"""Cobertura del import masivo de médicos por Excel: plantilla, preview (no
persiste), confirm (todo-o-nada), No. Médico explícito + secuencia, warnings
(D7) y escenarios de reintento/carrera. Espejo de
`apps/administracion/tests/test_rbac_users_api.py`
(`RbacUsersImportApiTests`), adaptado al mecanismo de autenticación ya
establecido en `test_medico_create_api.py` (`start_session` directo -- evita
los 409 intermitentes del flujo HTTP de login contra Redis)."""

import io
import uuid
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

import openpyxl
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, DetUsuarioCedula, SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import (
    CatTipoPersonal,
    Escuelas,
    Especialidades,
    Permisos,
    Roles,
)
from apps.medicos.models import (
    CatMedico,
    MedicoImportJob,
    RelMedicoCentro,
    RelMedicoEspecialidad,
)
from apps.medicos.services.medico_import_service import HEADERS as MEDICO_IMPORT_HEADERS

IMPORT_TEMPLATE_URL = "/api/v1/medicos/import/template"
IMPORT_PREVIEW_URL = "/api/v1/medicos/import/preview"
IMPORT_CONFIRM_URL = "/api/v1/medicos/import/confirm"
IMPORT_JOB_URL = "/api/v1/medicos/import/jobs/"

_KEYS = [
    "no", "usuario", "nom", "pat", "mat", "ced", "esc", "sexo", "fnac",
    "esp", "serv", "estatus",
]


def row(**kw):
    """Fila del Excel en el orden de HEADERS (claves = abreviaturas de _KEYS)."""
    unknown = set(kw) - set(_KEYS)
    assert not unknown, unknown
    return tuple(kw.get(k, "") for k in _KEYS)


def _medicos_xlsx_upload(rows, filename="import_medicos.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(MEDICO_IMPORT_HEADERS))
    for r in rows:
        ws.append(list(r))
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

        self.actor = self._create_usuario("admin_import_medicos", tipo_personal="Administrativo")
        RelUsuarioRol.objects.create(id_usuario=self.actor, id_rol=self.role, is_primary=True)
        self.auth_headers = self._auth_headers(self.actor)

    def _create_usuario(self, username, tipo_personal="Médico"):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("x"),
            est_activo=True,
        )
        tipo, _ = CatTipoPersonal.objects.get_or_create(
            name=tipo_personal, defaults={"is_active": True}
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, id_tipo_personal=tipo)
        return user

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

    def test_preview_reports_errors_and_warnings_without_persisting(self):
        valid_user = self._create_usuario("preview_medico_valid")
        before = CatMedico.objects.count()
        file = _medicos_xlsx_upload(
            [
                row(usuario=valid_user.usuario, estatus="Activo"),
                row(ced="123"),  # sin usuario, sin paterno ni nombre
                row(usuario="usuario_que_no_existe"),
                row(pat="López", nom="Juan"),  # sin cédula -> warning
            ]
        )

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CatMedico.objects.count(), before)
        self.assertEqual(response.data["totalRecords"], 4)
        self.assertEqual(response.data["totalErrores"], 2)
        self.assertEqual(response.data["totalWarnings"], 1)
        self.assertEqual(response.data["inserted"], 0)

        rows = response.data["rows"]
        self.assertEqual(rows[0]["errors"], [])
        self.assertEqual(rows[0]["warnings"], [])
        self.assertIn(
            "Nombre(s) es obligatorio cuando no se captura Usuario.", rows[1]["errors"]
        )
        self.assertTrue(any("no existe un usuario" in e.lower() for e in rows[2]["errors"]))
        self.assertEqual(rows[3]["errors"], [])
        self.assertEqual(len(rows[3]["warnings"]), 1)

    def test_preview_flags_invalid_estatus_instead_of_silently_defaulting(self):
        user = self._create_usuario("invalid_estatus_medico")
        file = _medicos_xlsx_upload([row(usuario=user.usuario, estatus="Jubilado")])

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totalErrores"], 1)
        data_row = response.data["rows"][0]
        self.assertIn(
            "Estatus del Médico 'Jubilado' no es válido. "
            "Valores permitidos: ACTIVO, VACACIONES, INCAPACIDAD, SUSPENDIDO, BAJA (o A / B).",
            data_row["errors"],
        )
        self.assertEqual(data_row["data"]["estatusMedico"], "ACTIVO")

    def test_preview_still_defaults_silently_when_tipo_medico_and_estatus_are_empty(self):
        user = self._create_usuario("empty_choice_defaults_silently")
        file = _medicos_xlsx_upload([row(usuario=user.usuario)])

        response = self._post_file(IMPORT_PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totalErrores"], 0)
        data_row = response.data["rows"][0]
        self.assertEqual(data_row["data"]["tipoMedico"], "CLINICA")
        self.assertEqual(data_row["data"]["estatusMedico"], "ACTIVO")

    # ── Confirm asíncrono (job + Celery) ─────────────────────────────────────

    def _confirm_and_wait(self, file):
        """
        Confirm asíncrono: POST encola (202) y la tarea Celery corre al hacer
        commit. En el test se ejecuta la tarea en línea (sin broker) y se
        devuelve el estado final del job tal como lo ve el polling.
        """
        from apps.medicos.tasks import procesar_import_medicos

        with patch("apps.medicos.views.medico_import_views.procesar_import_medicos") as task_mock:
            task_mock.delay.side_effect = lambda job_id: procesar_import_medicos(job_id)
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        self.assertEqual(response.data["status"], "PENDING")
        status_response = self.client.get(f"{IMPORT_JOB_URL}{response.data['jobId']}")
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        return status_response.data

    def test_confirm_encola_y_responde_202_sin_procesar(self):
        file = _medicos_xlsx_upload([row(no="7", pat="A", nom="B", ced="1")])

        with patch("apps.medicos.views.medico_import_views.procesar_import_medicos") as task_mock:
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job = MedicoImportJob.objects.get(id=response.data["jobId"])
        task_mock.delay.assert_called_once_with(str(job.id))
        self.assertEqual(job.status, MedicoImportJob.Status.PENDING)
        self.assertEqual(job.actor_id, self.actor.id_usuario)
        self.assertFalse(CatMedico.objects.filter(id=7).exists())

    def test_confirm_rechaza_si_hay_otro_import_en_curso(self):
        activo = MedicoImportJob.objects.create(
            file_name="otro.xlsx", status=MedicoImportJob.Status.RUNNING,
        )
        file = _medicos_xlsx_upload([row(no="7", pat="A", nom="B", ced="1")])

        with patch("apps.medicos.views.medico_import_views.procesar_import_medicos") as task_mock:
            response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "IMPORT_IN_PROGRESS")
        self.assertEqual(response.data["details"]["jobId"], str(activo.id))
        task_mock.delay.assert_not_called()

    def _job_pending_viejo(self, minutos=6, **fields):
        job = MedicoImportJob.objects.create(file_name="viejo.xlsx", **fields)
        MedicoImportJob.objects.filter(id=job.id).update(
            fch_alta=timezone.now() - timedelta(minutes=minutos)
        )
        return job

    def test_confirm_cierra_pending_que_el_worker_nunca_tomo_y_encola(self):
        viejo = self._job_pending_viejo()
        file = _medicos_xlsx_upload([row(no="7", pat="A", nom="B", ced="1")])

        with patch("apps.medicos.views.medico_import_views.procesar_import_medicos"):
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post_file(IMPORT_CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        viejo.refresh_from_db()
        self.assertEqual(viejo.status, MedicoImportJob.Status.ERROR)
        self.assertEqual(viejo.error_code, "WORKER_NO_DISPONIBLE")
        self.assertIsNotNone(viejo.fch_fin)

    def test_polling_cierra_pending_viejo_con_error_claro(self):
        viejo = self._job_pending_viejo()

        data = self.client.get(f"{IMPORT_JOB_URL}{viejo.id}").data

        self.assertEqual(data["status"], "ERROR")
        self.assertEqual(data["errorCode"], "WORKER_NO_DISPONIBLE")
        self.assertIn("Reinicia el worker", data["errorMessage"])

    def test_pending_reciente_y_running_viejo_no_se_cierran(self):
        reciente = self._job_pending_viejo(minutos=1)
        corriendo = self._job_pending_viejo(
            status=MedicoImportJob.Status.RUNNING, fch_inicio=timezone.now(),
        )

        self.assertEqual(self.client.get(f"{IMPORT_JOB_URL}{reciente.id}").data["status"], "PENDING")
        self.assertEqual(self.client.get(f"{IMPORT_JOB_URL}{corriendo.id}").data["status"], "RUNNING")

    def test_job_status_muestra_avance_vivo_de_la_cache(self):
        from apps.medicos.services import import_job_progress

        job = MedicoImportJob.objects.create(
            file_name="x.xlsx", status=MedicoImportJob.Status.RUNNING,
        )
        import_job_progress.set_progress(job.id, "SAVING", 1200, 2709)

        data = self.client.get(f"{IMPORT_JOB_URL}{job.id}").data

        self.assertEqual(
            (data["phase"], data["processed"], data["phaseTotal"]), ("SAVING", 1200, 2709)
        )
        self.assertIsNone(data["result"])
        import_job_progress.clear_progress(job.id)

    def test_use_case_reporta_avance_de_guardado_por_fila(self):
        from apps.medicos.uses_case.import_medicos import ConfirmMedicosImportUseCase

        calls = []
        file = _medicos_xlsx_upload(
            [row(no="1", pat="A", nom="UNO", ced="1"), row(pat="B", nom="DOS", ced="1")]
        )

        ConfirmMedicosImportUseCase().execute(
            file, self.actor, progress=lambda *args: calls.append(args),
        )

        saving = [c for c in calls if c[0] == "SAVING"]
        self.assertEqual(saving, [("SAVING", 0, 2), ("SAVING", 1, 2), ("SAVING", 2, 2)])
        self.assertEqual(calls[0], ("VALIDATING", 0, 0))

    def test_job_inexistente_es_404(self):
        response = self.client.get(f"{IMPORT_JOB_URL}{uuid.uuid4()}")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "IMPORT_JOB_NOT_FOUND")

    # ── Confirm: errores ─────────────────────────────────────────────────────

    def test_confirm_with_any_error_creates_nothing(self):
        before = CatMedico.objects.count()
        file = _medicos_xlsx_upload([row(usuario="usuario_que_no_existe_409")])

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "VALIDATION_FAILED")
        self.assertEqual(job["result"]["inserted"], 0)
        self.assertEqual(job["result"]["totalErrores"], 1)
        self.assertEqual(CatMedico.objects.count(), before)

    def test_preview_y_confirm_rechazan_usuario_que_no_es_medico(self):
        # S6.4: mismo gate que el alta manual (tipo_personal = Médico).
        admin = self._create_usuario("import_no_medico", tipo_personal="Administrativo")
        before = CatMedico.objects.count()
        file = _medicos_xlsx_upload([row(usuario=admin.usuario)])

        preview = self._post_file(IMPORT_PREVIEW_URL, file)
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["totalErrores"], 1)
        self.assertIn(
            "no tiene tipo de personal Médico", preview.data["rows"][0]["errors"][0]
        )

        file.seek(0)
        job = self._confirm_and_wait(file)
        self.assertEqual(job["status"], "VALIDATION_FAILED")
        self.assertEqual(job["result"]["inserted"], 0)
        self.assertEqual(CatMedico.objects.count(), before)

    def test_confirm_blocks_all_or_nothing_when_one_row_has_error(self):
        # Una fila válida + una con No. Médico duplicado en BD: no entra ninguna.
        CatMedico.objects.create(id=50)
        file = _medicos_xlsx_upload(
            [
                row(no="10", pat="A", nom="UNO", ced="1"),
                row(no="50", pat="B", nom="DOS", ced="1"),
            ]
        )

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "VALIDATION_FAILED")
        self.assertEqual(CatMedico.objects.count(), 1)
        self.assertFalse(CatMedico.objects.filter(id=10).exists())

    def test_confirm_archivo_invalido_termina_en_error(self):
        file = _medicos_xlsx_upload([row(no="1", pat="A", nom="B")])
        file.name = "import.csv"

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "ERROR")
        self.assertIsNotNone(job["errorCode"])

    # ── Confirm: creación ────────────────────────────────────────────────────

    def test_confirm_con_usuario_deja_campos_personales_null(self):
        user = self._create_usuario("bulk_medico_one")
        file = _medicos_xlsx_upload(
            [row(usuario=user.usuario, pat="Ignorado", nom="Ignorado",
                 serv="Cardiología", estatus="Activo")]
        )

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "SUCCESS")
        self.assertEqual(job["inserted"], 1)
        self.assertEqual(job["result"]["inserted"], 1)
        medico = CatMedico.objects.get(id_usuario=user)
        self.assertIsNone(medico.paterno)
        self.assertIsNone(medico.nombre)
        self.assertIsNone(medico.cedula_profesional)
        self.assertEqual(medico.tipo_medico, "CLINICA")
        self.assertEqual(medico.servicio, "Cardiología")
        self.assertIsNone(medico.observaciones)
        # El archivo se descarta al terminar.
        self.assertIsNone(MedicoImportJob.objects.get(id=job["jobId"]).file_content)

    def test_confirm_sin_usuario_guarda_datos_personales(self):
        esc = Escuelas.objects.create(code="UNAM", name="Universidad Nacional")
        file = _medicos_xlsx_upload(
            [row(no="2726", pat="López", mat="Ramírez", nom="Juan", ced="1234567",
                 esc=str(esc.id), sexo="M", fnac="15/03/1975", estatus="A")]
        )

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "SUCCESS")
        medico = CatMedico.objects.get(id=2726)
        self.assertIsNone(medico.id_usuario_id)
        self.assertEqual(
            (medico.paterno, medico.materno, medico.nombre, medico.cedula_profesional),
            ("López", "Ramírez", "Juan", "1234567"),
        )
        self.assertEqual(medico.id_escuela_id, esc.id)
        self.assertEqual(medico.sexo, "M")
        self.assertEqual(str(medico.fecha_nac), "1975-03-15")
        self.assertEqual(medico.estatus_medico, "ACTIVO")

    def test_confirm_estatus_b_crea_baja(self):
        file = _medicos_xlsx_upload([row(no="9", pat="A", nom="B", ced="1", estatus="B")])
        self._confirm_and_wait(file)
        self.assertEqual(CatMedico.objects.get(id=9).estatus_medico, "BAJA")

    def test_confirm_usa_no_medico_como_id_y_los_sin_numero_van_despues(self):
        user = self._create_usuario("sin_numero")
        file = _medicos_xlsx_upload(
            [
                row(usuario=user.usuario),  # sin No. Médico, primero en el archivo
                row(no="2726", pat="A", nom="UNO", ced="1"),
                row(no="40", pat="B", nom="DOS", ced="1"),
            ]
        )

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "SUCCESS")
        self.assertEqual(job["result"]["inserted"], 3)
        self.assertTrue(CatMedico.objects.filter(id=2726).exists())
        self.assertTrue(CatMedico.objects.filter(id=40).exists())
        # S1.5: la fila sin número toma el siguiente tras el máximo explícito.
        self.assertGreater(CatMedico.objects.get(id_usuario=user).id, 2726)

    def test_confirm_crea_especialidad_principal_y_ningun_centro(self):
        esp = Especialidades.objects.create(name="Cirugía")
        file = _medicos_xlsx_upload(
            [row(no="5", pat="A", nom="B", ced="1", esp=str(esp.id))]
        )

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "SUCCESS")
        # La plantilla ya no trae Clave Clínica: el centro se asigna en la ficha.
        self.assertFalse(RelMedicoCentro.objects.filter(medico_id=5).exists())
        rel_esp = RelMedicoEspecialidad.objects.get(medico_id=5)
        self.assertEqual(rel_esp.especialidad_id, esp.id)
        self.assertTrue(rel_esp.es_principal)

    def test_confirm_con_warnings_no_bloquea_y_crea_sin_relaciones(self):
        # Sin cédula = warning: no bloquea.
        file = _medicos_xlsx_upload([row(no="6", pat="A", nom="B")])

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "SUCCESS")
        self.assertEqual(job["result"]["inserted"], 1)
        self.assertEqual(job["result"]["totalWarnings"], 1)
        self.assertEqual(len(job["result"]["rows"][0]["warnings"]), 1)
        self.assertTrue(CatMedico.objects.filter(id=6).exists())
        self.assertFalse(RelMedicoCentro.objects.filter(medico_id=6).exists())
        self.assertFalse(RelMedicoEspecialidad.objects.filter(medico_id=6).exists())

    def test_confirm_bloquea_todo_si_especialidad_o_escuela_no_existen(self):
        before = CatMedico.objects.count()
        file = _medicos_xlsx_upload(
            [
                row(no="7", pat="A", nom="B", ced="1"),
                row(no="8", pat="C", nom="D", ced="1", esp="999999"),
                row(no="9", pat="E", nom="F", ced="1", esc="999999"),
            ]
        )

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "VALIDATION_FAILED")
        self.assertEqual(job["result"]["totalErrores"], 2)
        self.assertEqual(CatMedico.objects.count(), before)

    def test_confirm_con_usuario_agrega_cedula_principal_o_adicional(self):
        sin_cedula = self._create_usuario("sin_cedula")
        con_cedula = self._create_usuario("con_cedula")
        DetUsuarioCedula.objects.create(
            id_usuario=con_cedula, numero="ORIGINAL", tipo="PROFESIONAL",
            es_principal=True, orden=1,
        )
        file = _medicos_xlsx_upload(
            [
                row(usuario=sin_cedula.usuario, ced="NUEVA-1"),
                row(usuario=con_cedula.usuario, ced="NUEVA-2"),
            ]
        )

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "SUCCESS")
        # Sin cédulas previas: la del Excel queda como principal.
        creada = DetUsuarioCedula.objects.get(id_usuario=sin_cedula)
        self.assertEqual(creada.numero, "NUEVA-1")
        self.assertTrue(creada.es_principal)
        # Con cédula previa: se AGREGA como adicional, la original no se toca.
        self.assertEqual(
            list(
                DetUsuarioCedula.objects.filter(id_usuario=con_cedula)
                .order_by("orden")
                .values_list("numero", "es_principal", "orden")
            ),
            [("ORIGINAL", True, 1), ("NUEVA-2", False, 2)],
        )

    def test_confirm_con_usuario_no_duplica_cedula_ya_registrada(self):
        usuario = self._create_usuario("cedula_repetida")
        DetUsuarioCedula.objects.create(
            id_usuario=usuario, numero="ABC 123", tipo="PROFESIONAL",
            es_principal=True, orden=1,
        )
        file = _medicos_xlsx_upload([row(usuario=usuario.usuario, ced="abc123")])

        job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "SUCCESS")
        self.assertIn(
            "El usuario ya tiene registrada la cédula 'abc123': no se duplica.",
            job["result"]["rows"][0]["warnings"],
        )
        self.assertEqual(DetUsuarioCedula.objects.filter(id_usuario=usuario).count(), 1)

    def test_confirm_rolls_back_everything_if_one_row_fails_mid_transaction(self):
        usuarios = [self._create_usuario(f"rollback_medico_{i}") for i in range(5)]
        file = _medicos_xlsx_upload([row(usuario=u.usuario) for u in usuarios])
        before = CatMedico.objects.count()

        with patch(
            "apps.medicos.uses_case.import_medicos.MedicoRepository.exists_for_usuario"
        ) as exists_mock:
            # La fila 3 "revienta" la carrera: debe abortar TODO el lote,
            # incluidas las 2 filas ya insertadas en la misma transacción.
            exists_mock.side_effect = [False, False, True, False, False]

            job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "ERROR")
        self.assertEqual(job["errorCode"], "MEDICO_IMPORT_RACE")
        self.assertEqual(CatMedico.objects.count(), before)

    def test_confirm_rollback_con_ids_explicitos_no_deja_filas(self):
        # S1.3: falla una fila sin número (después de insertar las explícitas).
        user = self._create_usuario("rollback_explicito")
        file = _medicos_xlsx_upload(
            [row(no="100", pat="A", nom="UNO", ced="1"), row(usuario=user.usuario)]
        )

        with patch(
            "apps.medicos.uses_case.import_medicos.MedicoRepository.exists_for_usuario",
            return_value=True,
        ):
            job = self._confirm_and_wait(file)

        self.assertEqual(job["status"], "ERROR")
        self.assertFalse(CatMedico.objects.filter(id=100).exists())

    # ── Reintentos ───────────────────────────────────────────────────────────

    def test_confirm_retry_sin_usuario_ni_numero_does_not_duplicate(self):
        rows = [row(pat="Pérez", nom="Ana", ced="1")]

        first = self._confirm_and_wait(_medicos_xlsx_upload(rows))
        self.assertEqual(first["status"], "SUCCESS")

        retry = self._confirm_and_wait(_medicos_xlsx_upload(rows))

        self.assertEqual(retry["status"], "VALIDATION_FAILED")
        self.assertIn(
            "Ya existe un médico sin usuario con el nombre 'Pérez Ana'.",
            retry["result"]["rows"][0]["errors"],
        )
        self.assertEqual(CatMedico.objects.filter(id_usuario__isnull=True).count(), 1)

    def test_confirm_retry_con_no_medico_flags_existing_row(self):
        rows = [row(no="321", pat="Pérez", nom="Ana", ced="1")]

        first = self._confirm_and_wait(_medicos_xlsx_upload(rows))
        self.assertEqual(first["status"], "SUCCESS")
        retry = self._confirm_and_wait(_medicos_xlsx_upload(rows))

        self.assertEqual(retry["status"], "VALIDATION_FAILED")
        self.assertIn(
            "Ya existe un médico con el No. Médico 321.", retry["result"]["rows"][0]["errors"]
        )
        self.assertEqual(CatMedico.objects.count(), 1)

    def test_confirm_retry_after_success_flags_existing_rows_without_duplicating(self):
        user_a = self._create_usuario("retry_medico_a")
        user_b = self._create_usuario("retry_medico_b")
        rows = [row(usuario=user_a.usuario), row(usuario=user_b.usuario)]

        first = self._confirm_and_wait(_medicos_xlsx_upload(rows))
        self.assertEqual(first["status"], "SUCCESS")
        self.assertEqual(first["result"]["inserted"], 2)

        retry = self._confirm_and_wait(_medicos_xlsx_upload(rows))

        self.assertEqual(retry["status"], "VALIDATION_FAILED")
        self.assertEqual(retry["result"]["inserted"], 0)
        for r in retry["result"]["rows"]:
            self.assertIn("Este usuario ya tiene un perfil de médico.", r["errors"])
        self.assertEqual(CatMedico.objects.count(), 2)


@skipUnless(connection.vendor == "postgresql", "setval de la secuencia: solo Postgres")
class MedicoImportSequenceTests(TransactionTestCase):
    """S1.2 / R1: tras importar ids explícitos, la siguiente alta recibe max+1."""

    def test_siguiente_alta_toma_max_mas_uno(self):
        from apps.medicos.uses_case.import_medicos import ConfirmMedicosImportUseCase

        actor = SyUsuario.objects.create(
            usuario="seq_actor", correo="seq_actor@example.com",
            clave_hash=make_password("x"), est_activo=True,
        )
        file = _medicos_xlsx_upload(
            [
                row(no="2726", pat="A", nom="UNO", ced="1"),
                row(no="10", pat="B", nom="DOS", ced="1"),
            ]
        )

        result = ConfirmMedicosImportUseCase().execute(file, actor)

        self.assertFalse(result["has_errors"])
        self.assertEqual(CatMedico.objects.create().id, 2727)

    def test_import_en_tabla_vacia_deja_secuencia_en_max_mas_uno(self):
        from apps.medicos.uses_case.import_medicos import _sync_id_sequence

        CatMedico.objects.all().delete()
        CatMedico.objects.create(id=500)
        _sync_id_sequence()
        self.assertEqual(CatMedico.objects.create().id, 501)
