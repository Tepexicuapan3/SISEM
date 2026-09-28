from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import Areas, CatCentroAtencion, CatPermiso, CatRol, TiposAreas


class CatalogosAuthzTests(APITestCase):
    def setUp(self):
        # Ver comentario equivalente en test_catalogos_contract.py: sin esto
        # el policy_store cache-backed (bloqueo de sesion activa) sobrevive
        # entre tests y el 2o login en adelante falla con 409.
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

        self.role = CatRol.objects.create(
            rol="CATALOG_READER",
            desc_rol="Rol de catalogos",
            landing_route="/catalogos",
            is_active=True,
        )

        self.perm_read = CatPermiso.objects.create(
            codigo="admin:catalogos:centros_atencion:read",
            descripcion="Leer centros",
            is_active=True,
        )
        self.perm_create = CatPermiso.objects.create(
            codigo="admin:catalogos:centros_atencion:create",
            descripcion="Crear centros",
            is_active=True,
        )
        self.perm_area_read = CatPermiso.objects.create(
            codigo="admin:catalogos:areas:read",
            descripcion="Leer areas",
            is_active=True,
        )
        self.perm_area_create = CatPermiso.objects.create(
            codigo="admin:catalogos:areas:create",
            descripcion="Crear areas",
            is_active=True,
        )

        self.user = SyUsuario.objects.create(
            usuario="catalog_user",
            correo="catalog.user@example.com",
            clave_hash=make_password("Catalog_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=self.user,
            nombre="Catalog",
            paterno="User",
            materno="",
        )
        RelUsuarioRol.objects.create(id_usuario=self.user, id_rol=self.role, is_primary=True)

        self.center = CatCentroAtencion.objects.create(
            name="Centro Authz",
            code="CA-001",
            is_external=False,
            address="Direccion 1",
            is_active=True,
            created_by_id=self.user.id_usuario,
        )
        self.tipo_area = TiposAreas.objects.create(
            name="Tipo Authz",
            is_active=True,
            created_by_id=self.user.id_usuario,
        )
        self.area = Areas.objects.create(
            name="Area Authz",
            code=10,
            tipo_area=self.tipo_area,
            is_active=True,
            created_by_id=self.user.id_usuario,
        )

    def _login(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "catalog_user", "password": "Catalog_123456"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies
        return response

    def test_list_requires_authentication(self):
        response = self.client.get("/api/v1/care-centers/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")

    def test_list_requires_permission(self):
        self._login()

        response = self.client.get("/api/v1/care-centers/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "INSUFFICIENT_PERMISSIONS")

    def test_list_with_permission_succeeds(self):
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_read)
        self._login()

        response = self.client.get("/api/v1/care-centers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 1)

    def test_create_requires_csrf(self):
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_create)
        self._login()

        response = self.client.post(
            "/api/v1/care-centers/",
            {
                "name": "Centro Nuevo",
                "code": "CA-002",
                "isExternal": True,
                "address": "Direccion 2",
                "isActive": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "CSRF_INVALID")

    def test_create_with_permission_and_csrf_succeeds(self):
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_create)
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/care-centers/",
            {
                "name": "Centro Nuevo",
                "code": "CA-002",
                "centerType": "CLINICA",
                "isExternal": True,
                "address": "Direccion 2",
                "isActive": True,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "Centro Nuevo (CA-002)")

    def test_areas_list_requires_authentication(self):
        response = self.client.get("/api/v1/areas/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "TOKEN_INVALID")

    def test_areas_list_requires_permission(self):
        self._login()

        response = self.client.get("/api/v1/areas/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "INSUFFICIENT_PERMISSIONS")

    def test_areas_list_with_permission_succeeds(self):
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_area_read)
        self._login()

        response = self.client.get("/api/v1/areas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertGreaterEqual(len(response.data["items"]), 1)

    def test_areas_create_requires_csrf(self):
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_area_create)
        self._login()

        response = self.client.post(
            "/api/v1/areas/",
            {
                "name": "Area Nueva",
                "code": "99",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "CSRF_INVALID")

    def test_areas_create_with_permission_and_csrf_succeeds(self):
        RelRolPermiso.objects.create(id_rol=self.role, id_permiso=self.perm_area_create)
        login_response = self._login()
        csrf_token = login_response.cookies.get(CSRF_COOKIE).value

        response = self.client.post(
            "/api/v1/areas/",
            {
                "name": "Area Nueva",
                "code": "99",
                "idTipoArea": self.tipo_area.id,
            },
            format="json",
            HTTP_X_CSRF_TOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "Area Nueva")
