from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import (
    Areas,
    CatCentroAtencion,
    Consultorios,
    Permisos,
    Roles,
    TiposAreas,
    Turnos,
)


class CatalogosContractTests(APITestCase):
    def setUp(self):
        # Sin esto, el login real de cada test queda sujeto al policy_store
        # cache-backed (bloqueo de sesion activa por user_id, throttle de
        # intentos) -- Django NO lo limpia entre tests (no es parte del
        # rollback de transaccion de APITestCase), y SQLite reutiliza el
        # mismo id_usuario autoincremental tras cada rollback, asi que el
        # login del 2o test en adelante choca con el "active session" que
        # dejo el 1er test y falla con 409 SESSION_ALREADY_ACTIVE. Mismo
        # criterio que apps.authentication.tests.test_auth_api.py.
        cache.clear()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cat_areas (
                    id_area INTEGER PRIMARY KEY AUTOINCREMENT,
                    area VARCHAR(150) NOT NULL,
                    id_tparea BIGINT NOT NULL,
                    est_activo BOOLEAN NOT NULL DEFAULT 1,
                    fch_alta DATETIME,
                    fch_modf DATETIME,
                    fch_baja DATETIME,
                    usr_alta BIGINT,
                    usr_modf BIGINT,
                    usr_baja BIGINT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cat_turnos (
                    id_trno INTEGER PRIMARY KEY AUTOINCREMENT,
                    turno VARCHAR(50) NOT NULL,
                    est_activo BOOLEAN NOT NULL DEFAULT 1,
                    fch_alta DATETIME,
                    fch_modf DATETIME,
                    fch_baja DATETIME,
                    usr_alta BIGINT,
                    usr_modf BIGINT,
                    usr_baja BIGINT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cat_consultorios (
                    id_consult INTEGER PRIMARY KEY AUTOINCREMENT,
                    no_consult INTEGER NOT NULL,
                    id_trno BIGINT NOT NULL,
                    id_centro_atencion BIGINT NOT NULL,
                    consult VARCHAR(50) NOT NULL,
                    est_activo BOOLEAN NOT NULL DEFAULT 1,
                    fch_alta DATETIME,
                    fch_modf DATETIME,
                    fch_baja DATETIME,
                    usr_alta BIGINT,
                    usr_modf BIGINT,
                    usr_baja BIGINT
                )
                """
            )

        self.user = SyUsuario.objects.create(
            usuario="admincatalog",
            correo="admin.catalog@example.com",
            clave_hash=make_password("Admin_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Admin",
            paterno="Catalog",
            materno="",
        )

        role = Roles.objects.create(
            rol="ADMIN_CATALOG",
            desc_rol="Administrador de catalogos",
            landing_route="/admin/catalogos",
            is_admin=True,
            is_active=True,
        )
        RelUsuarioRol.objects.create(
            id_usuario=self.user,
            id_rol=role,
            is_primary=True,
        )

        Permisos.objects.create(
            codigo="admin:catalogos:centros_atencion:read",
            descripcion="Leer centros",
            is_active=True,
        )
        Permisos.objects.create(
            codigo="admin:catalogos:areas:read",
            descripcion="Leer areas",
            is_active=True,
        )

        self.center = CatCentroAtencion.objects.create(
            name="Centro Contract",
            code="CC-001",
            is_external=False,
            address="Av. Siempre Viva 123",
            is_active=True,
            created_by_id=self.user.id_usuario,
        )
        self.tipo_area = TiposAreas.objects.create(
            name="Tipo Contract",
            is_active=True,
            created_by_id=self.user.id_usuario,
        )
        self.area = Areas.objects.create(
            name="Urgencias",
            code=10,
            tipo_area=self.tipo_area,
            is_active=True,
            created_by_id=self.user.id_usuario,
        )
        self.turn = Turnos.objects.create(
            name="Matutino",
            is_active=True,
            created_by_id=self.user.id_usuario,
        )
        self.consultorio = Consultorios.objects.create(
            name="Consultorio Contract",
            numero=301,
            id_turn=self.turn,
            id_center=self.center,
            is_active=True,
            created_by_id=self.user.id_usuario,
        )

        login_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "admincatalog", "password": "Admin_123456"},
            format="json",
        )
        assert login_response.status_code == status.HTTP_200_OK
        self.client.cookies = login_response.cookies
        self.csrf_token = login_response.cookies.get(CSRF_COOKIE).value

    def test_care_centers_list_contract(self):
        response = self.client.get("/api/v1/care-centers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIn("page", response.data)
        self.assertIn("pageSize", response.data)
        self.assertIn("total", response.data)
        self.assertIn("totalPages", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 1)

        item = response.data["items"][0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("code", item)
        self.assertIn("isExternal", item)
        self.assertIn("isActive", item)

    def test_care_centers_detail_contract(self):
        response = self.client.get(f"/api/v1/care-centers/{self.center.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("careCenter", response.data)
        center = response.data["careCenter"]
        self.assertEqual(center["id"], self.center.id)
        self.assertEqual(center["name"], "Centro Contract")
        self.assertIn("address", center)
        self.assertIn("createdAt", center)
        self.assertIn("updatedAt", center)

    def test_create_care_center_contract(self):
        response = self.client.post(
            "/api/v1/care-centers/",
            {
                "name": "Centro Norte",
                "code": "CC-002",
                "centerType": "CLINICA",
                "isExternal": True,
                "address": "Calle Norte 55",
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "Centro Norte (CC-002)")

    def test_update_care_center_contract(self):
        response = self.client.put(
            f"/api/v1/care-centers/{self.center.id}/",
            {
                "name": "Centro Contract Actualizado",
                "code": "CC-001",
                "isExternal": False,
                "address": "Av. Actualizada 555",
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("careCenter", response.data)
        self.assertEqual(
            response.data["careCenter"]["name"],
            "Centro Contract Actualizado",
        )

    def test_delete_care_center_contract(self):
        response = self.client.delete(
            f"/api/v1/care-centers/{self.center.id}/",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"success": True})

    def test_care_centers_invalid_sort_by_returns_contract_error(self):
        response = self.client.get(
            "/api/v1/care-centers/?sortBy=invalidField",
            HTTP_X_REQUEST_ID="req-catalog-123",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["requestId"], "req-catalog-123")
        self.assertIn("details", response.data)

    def test_care_centers_invalid_pagination_format_returns_invalid_format(self):
        response = self.client.get("/api/v1/care-centers/?page=uno&pageSize=diez")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "INVALID_FORMAT")

    def test_care_centers_pagination_out_of_range_returns_validation_error(self):
        response = self.client.get("/api/v1/care-centers/?page=0&pageSize=101")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_care_centers_invalid_sort_order_returns_validation_error(self):
        response = self.client.get("/api/v1/care-centers/?sortOrder=up")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_care_centers_invalid_is_active_returns_validation_error(self):
        response = self.client.get("/api/v1/care-centers/?isActive=quizas")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_care_centers_search_is_active_and_desc_sort(self):
        CatCentroAtencion.objects.create(
            name="Centro Inactivo",
            code="CC-099",
            is_external=False,
            address="Calle Inactiva",
            is_active=False,
            created_by_id=self.user.id_usuario,
        )

        response = self.client.get(
            "/api/v1/care-centers/?search=Centro&isActive=true&sortBy=name&sortOrder=desc"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total"], 1)
        self.assertTrue(all(item["isActive"] for item in response.data["items"]))

    def test_create_care_center_validation_error(self):
        response = self.client.post(
            "/api/v1/care-centers/",
            {
                "isExternal": True,
                "address": "Sin nombre",
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_care_center_detail_not_found(self):
        response = self.client.get("/api/v1/care-centers/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "CARE_CENTER_NOT_FOUND")

    def test_update_care_center_not_found(self):
        response = self.client.put(
            "/api/v1/care-centers/999999/",
            {
                "name": "No existe",
                "code": "CC-404",
                "isExternal": False,
                "address": "N/A",
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "CARE_CENTER_NOT_FOUND")

    def test_update_care_center_validation_error(self):
        response = self.client.put(
            f"/api/v1/care-centers/{self.center.id}/",
            {
                "name": "Centro Contract",
                "code": "CC-001",
                "isExternal": "no-bool",
                "address": "Av. Actualizada 555",
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_update_care_center_duplicate_name_returns_conflict(self):
        duplicated = CatCentroAtencion.objects.create(
            name="Centro Duplicado",
            code="CC-777",
            is_external=False,
            address="Calle Duplicada",
            is_active=True,
            created_by_id=self.user.id_usuario,
        )

        response = self.client.put(
            f"/api/v1/care-centers/{self.center.id}/",
            {
                "name": duplicated.name,
                "code": "CC-001",
                "isExternal": False,
                "address": "Av. Actualizada 555",
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "CARE_CENTER_EXISTS")

    def test_delete_care_center_not_found(self):
        response = self.client.delete(
            "/api/v1/care-centers/999999/",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "CARE_CENTER_NOT_FOUND")

    def test_areas_list_contract(self):
        response = self.client.get("/api/v1/areas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 1)

        item = response.data["items"][0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("code", item)
        self.assertIn("isActive", item)

    def test_areas_detail_contract(self):
        response = self.client.get(f"/api/v1/areas/{self.area.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("area", response.data)
        area = response.data["area"]
        self.assertEqual(area["id"], self.area.id)
        self.assertEqual(area["name"], "Urgencias")
        self.assertEqual(area["code"], "10")
        self.assertIn("createdAt", area)
        self.assertIn("updatedAt", area)

    def test_create_area_contract(self):
        response = self.client.post(
            "/api/v1/areas/",
            {
                "name": "Farmacia",
                "code": 20,
                "idTipoArea": self.tipo_area.id,
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "Farmacia")

    def test_areas_duplicate_name_returns_409(self):
        response = self.client.post(
            "/api/v1/areas/",
            {
                "name": "Urgencias",
                "code": 30,
                "idTipoArea": self.tipo_area.id,
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "AREAS_EXISTS")

    def test_consulting_rooms_list_contract(self):
        response = self.client.get("/api/v1/consulting-rooms/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 1)

        item = response.data["items"][0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("numero", item)
        self.assertIn("isActive", item)

    def test_consulting_rooms_list_regression_no_ghost_folio_column_error(self):
        """
        Regression guard:
        GET /consulting-rooms must not raise 500 due to stale center column mapping
        (legacy `folio` vs current `clues`).
        """
        response = self.client.get("/api/v1/consulting-rooms/?page=1&pageSize=10")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIsInstance(response.data["items"], list)

    def test_consulting_room_detail_contract(self):
        response = self.client.get(f"/api/v1/consulting-rooms/{self.consultorio.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("consultingRoom", response.data)
        consultorio = response.data["consultingRoom"]

        self.assertEqual(consultorio["id"], self.consultorio.id)
        self.assertEqual(consultorio["name"], self.consultorio.name)
        self.assertEqual(consultorio["numero"], self.consultorio.numero)
        self.assertIn("turn", consultorio)
        self.assertIn("center", consultorio)
        self.assertIn("createdAt", consultorio)
        self.assertIn("updatedAt", consultorio)

    def test_create_consulting_room_contract(self):
        response = self.client.post(
            "/api/v1/consulting-rooms/",
            {
                "name": "Consultorio Norte",
                "numero": 401,
                "idTurn": self.turn.id,
                "idCenter": self.center.id,
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "Consultorio Norte")
