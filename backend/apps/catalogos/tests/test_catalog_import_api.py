"""
Integration tests for the generic catalog-import HTTP surface
(`GET {slug}/import/template/`, `POST {slug}/import/preview/`,
`POST {slug}/import/confirm/`), exercised end-to-end through the Django
test client against sqlite `:memory:` (see `config/settings.py`, `if "test"
in sys.argv`). Mirrors the auth/permission setup used by
`apps/administracion/tests/test_rbac_authz_matrix.py` and
`apps/catalogos/tests/test_catalogos_contract.py`.
"""

import io

import openpyxl
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import CatPermiso, CatRol, Especialidades

SPECIALTIES_HEADERS = ["ID", "Nombre", "Activo"]

TEMPLATE_URL = "/api/v1/specialties/import/template/"
PREVIEW_URL = "/api/v1/specialties/import/preview/"
CONFIRM_URL = "/api/v1/specialties/import/confirm/"


def _xlsx_upload(headers, rows, filename="import.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile(
        filename,
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class _AuthenticatedImportTestCase(APITestCase):
    """Logs in a user holding both `admin:catalogos:especialidades:read` and
    `...:create` (Decision 2 in the design: import reuses read/create, no new
    permission string)."""

    def setUp(self):
        self.role = CatRol.objects.create(
            rol="CATALOG_IMPORT_ROLE",
            desc_rol="Rol con permisos de import de especialidades",
            landing_route="/admin/catalogos",
            is_active=True,
        )
        self.perm_read = CatPermiso.objects.get_or_create(codigo="admin:catalogos:especialidades:read", defaults=dict(descripcion="Leer especialidades", is_active=True))[0]
        self.perm_create = CatPermiso.objects.get_or_create(codigo="admin:catalogos:especialidades:create", defaults=dict(descripcion="Crear especialidades", is_active=True))[0]
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_read)
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_create)

        self.user = SyUsuario.objects.create(
            usuario="import_user",
            correo="import.user@example.com",
            clave_hash=make_password("Import_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=self.user, nombre="Import", paterno="User", materno="")
        RelUsuarioRol.objects.create(id_usuario=self.user, id_rol=self.role, is_primary=True)

        # Redis (sesion unica) no se limpia entre tests como la DB sqlite;
        # un id_usuario reciclado por el autoincrement puede arrastrar una
        # sesion "activa" de un test anterior y el login choca con
        # SESSION_ALREADY_ACTIVE (409). Mismo patron que
        # test_rbac_authz_matrix.py.
        PolicyStore().clear_active_session(self.user.id_usuario)

        login_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "import_user", "password": "Import_123456"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.client.cookies = login_response.cookies
        self.csrf_token = login_response.cookies.get(CSRF_COOKIE).value

    def _post_file(self, url, file, **extra_fields):
        payload = {"file": file, **extra_fields}
        return self.client.post(url, payload, HTTP_X_CSRF_TOKEN=self.csrf_token)


class CatalogImportTemplateApiTests(_AuthenticatedImportTestCase):
    def test_template_download_matches_catalog_columns_exactly(self):
        response = self.client.get(TEMPLATE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        headers = [cell.value for cell in wb.active[1]]
        self.assertEqual(headers, SPECIALTIES_HEADERS)


class CatalogImportPreviewDoesNotWriteTests(_AuthenticatedImportTestCase):
    def test_preview_leaves_catalog_row_count_unchanged(self):
        before = Especialidades.objects.count()
        file = _xlsx_upload(
            SPECIALTIES_HEADERS,
            [
                ["1", "Cardiología", "Si"],
                ["abc", "Pediatría", "Si"],  # ID invalido
            ],
        )

        response = self._post_file(PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Especialidades.objects.count(), before)
        self.assertEqual(response.data["total_records"], 2)
        self.assertEqual(response.data["total_errores"], 1)
        self.assertEqual(response.data["inserted"], 0)

    def test_preview_response_shape_echoes_fields_plus_error(self):
        file = _xlsx_upload(SPECIALTIES_HEADERS, [["1", "Cardiología", "Si"]])

        response = self._post_file(PREVIEW_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["rows"][0]
        self.assertEqual(row["ID"], 1)
        self.assertEqual(row["Nombre"], "Cardiología")
        self.assertEqual(row["Activo"], "Si")
        self.assertEqual(row["ERROR"], "")


class CatalogImportConfirmAllOrNothingTests(_AuthenticatedImportTestCase):
    def test_one_error_row_blocks_the_whole_batch(self):
        before = Especialidades.objects.count()
        file = _xlsx_upload(
            SPECIALTIES_HEADERS,
            [
                ["1", "Cardiología", "Si"],
                ["2", "", "Si"],  # Nombre vacio -> error
            ],
        )

        response = self._post_file(CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "IMPORT_HAS_ERRORS")
        self.assertEqual(response.data["inserted"], 0)
        self.assertEqual(Especialidades.objects.count(), before)

    def test_all_valid_batch_inserts_atomically_with_explicit_ids_gaps_preserved(self):
        given_ids = [1, 2, 3, 7, 8, 15, 16, 20]
        rows = [[str(i), f"Especialidad {i}", "Si"] for i in given_ids]
        file = _xlsx_upload(SPECIALTIES_HEADERS, rows)

        response = self._post_file(CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_errores"], 0)
        self.assertEqual(response.data["inserted"], len(given_ids))
        stored_ids = sorted(Especialidades.objects.values_list("id", flat=True))
        self.assertEqual(stored_ids, given_ids)


class CatalogImportConfirmSecurityTests(_AuthenticatedImportTestCase):
    """Covers the deliberate CIES-precedent fix: confirm accepts ONLY the
    file (multipart), never row data, and always re-validates server-side."""

    def test_confirm_without_prior_preview_call_still_rejects_invalid_file(self):
        before = Especialidades.objects.count()
        file = _xlsx_upload(
            SPECIALTIES_HEADERS,
            [
                ["1", "Cardiología", "Si"],
                ["-1", "Pediatría", "Si"],  # ID invalido, jamas paso por preview
            ],
        )

        response = self._post_file(CONFIRM_URL, file)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["inserted"], 0)
        self.assertEqual(Especialidades.objects.count(), before)

    def test_confirm_ignores_any_client_supplied_row_or_error_data(self):
        # El endpoint solo acepta `file` (multipart); si el cliente igual
        # manda un payload extra simulando filas ya validadas, el servidor
        # las ignora por completo y re-corre parse_and_validate sobre el
        # archivo real.
        file = _xlsx_upload(SPECIALTIES_HEADERS, [["1", "Cardiología", "true"]])  # Activo invalido

        response = self._post_file(
            CONFIRM_URL,
            file,
            rows='[{"ID": 1, "Nombre": "Cardiología", "Activo": "Si", "ERROR": ""}]',
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["inserted"], 0)
        self.assertEqual(Especialidades.objects.count(), 0)

    def test_confirm_rechecks_id_collision_that_appeared_after_preview(self):
        preview_file = _xlsx_upload(SPECIALTIES_HEADERS, [["9", "Cardiología", "Si"]])
        preview_response = self._post_file(PREVIEW_URL, preview_file)
        self.assertEqual(preview_response.data["total_errores"], 0)

        # Otro proceso inserta el ID 9 entre el preview y el confirm.
        Especialidades.objects.create(id=9, name="Insertado por otro proceso", is_active=True)

        confirm_file = _xlsx_upload(SPECIALTIES_HEADERS, [["9", "Cardiología", "Si"]])
        confirm_response = self._post_file(CONFIRM_URL, confirm_file)

        self.assertEqual(confirm_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(confirm_response.data["inserted"], 0)
        self.assertEqual(Especialidades.objects.count(), 1)


class CatalogImportPermissionTests(APITestCase):
    """A user with no `especialidades` permissions at all: template requires
    `:read`, preview/confirm require `:create` — same single-permission-family
    the frontend gate uses (Decision 2), enforced here on the backend."""

    def setUp(self):
        self.role = CatRol.objects.create(
            rol="CATALOG_IMPORT_NO_PERMS",
            desc_rol="Rol sin permisos de import",
            landing_route="/admin/catalogos",
            is_active=True,
        )
        self.user = SyUsuario.objects.create(
            usuario="no_perms_user",
            correo="no.perms@example.com",
            clave_hash=make_password("NoPerms_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=self.user, nombre="No", paterno="Perms", materno="")
        RelUsuarioRol.objects.create(id_usuario=self.user, id_rol=self.role, is_primary=True)

        PolicyStore().clear_active_session(self.user.id_usuario)

        login_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "no_perms_user", "password": "NoPerms_123456"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.client.cookies = login_response.cookies
        self.csrf_token = login_response.cookies.get(CSRF_COOKIE).value

    def test_template_without_read_permission_is_403(self):
        response = self.client.get(TEMPLATE_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "INSUFFICIENT_PERMISSIONS")

    def test_preview_without_create_permission_is_403(self):
        file = _xlsx_upload(SPECIALTIES_HEADERS, [["1", "Cardiología", "Si"]])

        response = self.client.post(PREVIEW_URL, {"file": file}, HTTP_X_CSRF_TOKEN=self.csrf_token)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "INSUFFICIENT_PERMISSIONS")

    def test_confirm_without_create_permission_is_403(self):
        file = _xlsx_upload(SPECIALTIES_HEADERS, [["1", "Cardiología", "Si"]])

        response = self.client.post(CONFIRM_URL, {"file": file}, HTTP_X_CSRF_TOKEN=self.csrf_token)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "INSUFFICIENT_PERMISSIONS")
        self.assertEqual(Especialidades.objects.count(), 0)
