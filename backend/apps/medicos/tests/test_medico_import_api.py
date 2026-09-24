"""Cobertura del import masivo de médicos por Excel: plantilla, preview (no
persiste), confirm (todo-o-nada) y sus escenarios de reintento/carrera.
Espejo de `apps/administracion/tests/test_rbac_users_api.py`
(`RbacUsersImportApiTests`, línea ~1856+), adaptado al mecanismo de
autenticación ya establecido en `test_medico_create_api.py`
(`start_session` directo -- evita los 409 intermitentes del flujo HTTP de
login contra Redis, según su propio docstring)."""

import io
from unittest.mock import patch

import openpyxl
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import Permisos, Roles
from apps.medicos.models import CatMedico
from apps.medicos.services.medico_import_service import HEADERS as MEDICO_IMPORT_HEADERS

IMPORT_TEMPLATE_URL = "/api/v1/medicos/import/template"
IMPORT_PREVIEW_URL = "/api/v1/medicos/import/preview"
IMPORT_CONFIRM_URL = "/api/v1/medicos/import/confirm"


def _medicos_xlsx_upload(rows, filename="import_medicos.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(MEDICO_IMPORT_HEADERS))
    for row in rows:
        ws.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile(
        filename,
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class MedicoImportApiTests(APITestCase):
    def setUp(self):
        self.role, _ = Roles.objects.get_or_create(
            rol="ADMIN_MEDICOS_IMPORT_TEST",
            defaults={"desc_rol": "Admin import medicos (test)", "landing_route": "/admin"},
        )
        permiso, _ = Permisos.objects.get_or_create(
            codigo="admin:gestion:medicos:create",
            defaults={"descripcion": "Crear medicos", "is_active": True},
        )
        RelRolPermiso.objects.get_or_create(id_rol=self.role, id_permiso=permiso)

        self.actor = self._create_usuario("admin_import_medicos")
        RelUsuarioRol.objects.create(id_usuario=self.actor, id_rol=self.role, is_primary=True)
        self.auth_headers = self._auth_headers(self.actor)

    def _create_usuario(self, username):
        return SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("x"),
            est_activo=True,
        )

    def _auth_headers(self, user):
        access, _refresh, _sid = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _post_file(self, url, file):
        return self.client.post(url, {"file": file}, **self.auth_headers)

    # ── Plantilla ────────────────────────────────────────────────────────────

    def test_template_download_has_expected_headers(self):
        response = self.client.get(IMPORT_TEMPLATE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        headers = [cell.value for cell in wb.active[1]]
        self.assertEqual(headers, MEDICO_IMPORT_HEADERS)

    # ── Preview ──────────────────────────────────────────────────────────────

    def test_preview_reports_valid_and_invalid_rows_without_persisting(self):
        valid_user = self._create_usuario("preview_medico_valid")
        before = CatMedico.objects.count()
        file = _medicos_xlsx_upload(
            [
                ("", valid_user.usuario, "", "", "", "Activo", ""),
                ("", "", "", "", "", "", ""),
                ("", "usuario_que_no_existe", "", "", "", "", ""),
            ]
        )

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CatMedico.objects.count(), before)
        self.assertEqual(response.data["totalRecords"], 3)
        self.assertEqual(response.data["totalErrores"], 2)
        self.assertEqual(response.data["inserted"], 0)

        rows = response.data["rows"]
        self.assertEqual(rows[0]["errors"], [])
        self.assertIn("Usuario (Login del sistema) es obligatorio.", rows[1]["errors"])
        self.assertTrue(
            any("no existe un usuario" in e.lower() for e in rows[2]["errors"])
        )

    def test_preview_flags_duplicate_legacy_code_in_file(self):
        user_a = self._create_usuario("dup_legacy_a")
        user_b = self._create_usuario("dup_legacy_b")
        file = _medicos_xlsx_upload(
            [
                ("E00000", user_a.usuario, "", "", "", "", ""),
                ("e00000", user_b.usuario, "", "", "", "", ""),
            ]
        )

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for row in response.data["rows"]:
            self.assertIn(
                "ID del Médico duplicado en el archivo.", row["errors"]
            )

    def test_preview_does_not_treat_e00000_or_h99999_as_sentinels(self):
        user_a = self._create_usuario("real_key_a")
        user_b = self._create_usuario("real_key_b")
        file = _medicos_xlsx_upload(
            [
                ("E00000", user_a.usuario, "", "", "", "", ""),
                ("H99999", user_b.usuario, "", "", "", "", ""),
            ]
        )

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totalErrores"], 0)
        self.assertEqual(response.data["rows"][0]["data"]["legacyCdMedico"], "E00000")
        self.assertEqual(response.data["rows"][1]["data"]["legacyCdMedico"], "H99999")

    def test_preview_flags_invalid_tipo_medico_instead_of_silently_defaulting(self):
        # CRITICAL de verify: un typo en Tipo de Médico caía al default
        # (CLINICA) sin marcar error de fila -- el usuario no tenia forma de
        # notarlo en el preview. Debe quedar visible como error.
        user = self._create_usuario("invalid_tipo_medico")
        file = _medicos_xlsx_upload(
            [("", user.usuario, "", "Clinca", "", "Activo", "")]
        )

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totalErrores"], 1)
        row = response.data["rows"][0]
        self.assertIn(
            "Tipo de Médico 'Clinca' no es válido. "
            "Valores permitidos: CLINICA, HOSPITAL, AMBOS.",
            row["errors"],
        )
        # Sigue resolviendo al default para no romper el resto de la fila,
        # pero queda marcada con error -- no se ve identica a una fila valida.
        self.assertEqual(row["data"]["tipoMedico"], "CLINICA")

    def test_preview_flags_invalid_estatus_instead_of_silently_defaulting(self):
        user = self._create_usuario("invalid_estatus_medico")
        file = _medicos_xlsx_upload(
            [("", user.usuario, "", "", "", "Jubilado", "")]
        )

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totalErrores"], 1)
        row = response.data["rows"][0]
        self.assertIn(
            "Estatus del Médico 'Jubilado' no es válido. "
            "Valores permitidos: ACTIVO, VACACIONES, INCAPACIDAD, SUSPENDIDO, BAJA.",
            row["errors"],
        )
        self.assertEqual(row["data"]["estatusMedico"], "ACTIVO")

    def test_preview_still_defaults_silently_when_tipo_medico_and_estatus_are_empty(self):
        # No tocar el comportamiento intencional y documentado: vacio ->
        # default, sin error de fila (solo un valor NO-vacio e invalido
        # debe marcar error).
        user = self._create_usuario("empty_choice_defaults_silently")
        file = _medicos_xlsx_upload([("", user.usuario, "", "", "", "", "")])

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totalErrores"], 0)
        row = response.data["rows"][0]
        self.assertEqual(row["data"]["tipoMedico"], "CLINICA")
        self.assertEqual(row["data"]["estatusMedico"], "ACTIVO")

    # ── Confirm ──────────────────────────────────────────────────────────────

    def test_confirm_with_any_error_creates_nothing(self):
        before = CatMedico.objects.count()
        # Fila con Usuario inexistente en vez de vacío: una fila totalmente
        # en blanco la descarta `pandas.read_excel` como línea final vacía
        # (mismo comportamiento que sufriría el import de usuarios con una
        # fila así) -- no es un bug de este import, así que el archivo de
        # prueba usa una fila con contenido real para forzar el error.
        file = _medicos_xlsx_upload([("", "usuario_que_no_existe_409", "", "", "", "", "")])

        response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "IMPORT_HAS_ERRORS")
        self.assertEqual(response.data["inserted"], 0)
        self.assertEqual(CatMedico.objects.count(), before)

    def test_confirm_blocks_all_or_nothing_when_tipo_medico_or_estatus_is_invalid(self):
        user = self._create_usuario("invalid_choice_blocks_confirm")
        before = CatMedico.objects.count()
        file = _medicos_xlsx_upload([("", user.usuario, "", "Clinca", "", "", "")])

        response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "IMPORT_HAS_ERRORS")
        self.assertEqual(response.data["inserted"], 0)
        self.assertEqual(CatMedico.objects.count(), before)

    def test_confirm_creates_all_medicos_when_every_row_is_valid(self):
        user_one = self._create_usuario("bulk_medico_one")
        user_two = self._create_usuario("bulk_medico_two")
        file = _medicos_xlsx_upload(
            [
                ("E00000", user_one.usuario, "Dr. Uno", "Hospital", "Cardiología", "Activo", "obs uno"),
                ("S/C", user_two.usuario, "", "", "", "", ""),
            ]
        )

        response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["inserted"], 2)
        self.assertEqual(response.data["totalErrores"], 0)

        medico_one = CatMedico.objects.get(id_usuario=user_one)
        self.assertEqual(medico_one.legacy_cd_medico, "E00000")
        self.assertEqual(medico_one.nombre_display, "Dr. Uno")
        self.assertEqual(medico_one.tipo_medico, "HOSPITAL")
        self.assertEqual(medico_one.servicio, "Cardiología")
        self.assertEqual(medico_one.estatus_medico, "ACTIVO")
        self.assertEqual(medico_one.observaciones, "obs uno")

        medico_two = CatMedico.objects.get(id_usuario=user_two)
        self.assertIsNone(medico_two.legacy_cd_medico)
        self.assertEqual(medico_two.tipo_medico, "CLINICA")
        self.assertEqual(medico_two.estatus_medico, "ACTIVO")

    def test_confirm_rolls_back_everything_if_one_row_fails_mid_transaction(self):
        usuarios = [self._create_usuario(f"rollback_medico_{i}") for i in range(5)]
        file = _medicos_xlsx_upload(
            [("", u.usuario, "", "", "", "", "") for u in usuarios]
        )
        before = CatMedico.objects.count()

        with patch(
            "apps.medicos.uses_case.import_medicos.MedicoRepository.exists_for_usuario"
        ) as exists_mock:
            # Filas 1 y 2 pasan (False = todavia no tiene medico); la fila 3
            # "revienta" la carrera (True = alguien mas ya lo vinculo entre
            # preview y confirm) -- debe abortar TODO el lote, incluidas las
            # 2 filas ya insertadas en esta misma transaccion atomica.
            exists_mock.side_effect = [False, False, True, False, False]

            response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["code"], "MEDICO_IMPORT_RACE")
        self.assertEqual(CatMedico.objects.count(), before)

    def test_confirm_retry_after_success_flags_existing_rows_without_duplicating(self):
        user_a = self._create_usuario("retry_medico_a")
        user_b = self._create_usuario("retry_medico_b")
        rows = [
            ("", user_a.usuario, "", "", "", "", ""),
            ("", user_b.usuario, "", "", "", "", ""),
        ]

        first = self._post_file(IMPORT_CONFIRM_URL, _medicos_xlsx_upload(rows))
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["inserted"], 2)

        retry = self._post_file(IMPORT_CONFIRM_URL, _medicos_xlsx_upload(rows))

        self.assertEqual(retry.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(retry.data["inserted"], 0)
        for row in retry.data["rows"]:
            self.assertIn("Este usuario ya tiene un perfil de médico.", row["errors"])
        self.assertEqual(CatMedico.objects.count(), 2)
