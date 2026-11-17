"""
Listado del catalogo CIE-10 (`GET /api/v1/cies/`) para la pantalla de
administracion: paginado como el resto de catalogos, busqueda en el
servidor (el catalogo oficial ronda 14 mil claves) y la clave se encuentra
escrita con o sin punto (`E11.9` = `E119`, formato DGIS guardado).
"""

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCies, CatPermiso, CatRol

LIST_URL = "/api/v1/cies/"


class CiesListApiTests(APITestCase):
    def setUp(self):
        self._login_with(["admin:catalogos:cies:read"])
        now = timezone.now()
        for code, description, version, active in [
            ("E119", "DIABETES MELLITUS NO INSULINODEPENDIENTE, SIN MENCIÓN DE COMPLICACIÓN", "CIE-10", True),
            ("I10", "HIPERTENSION", "CIE10", True),
            ("J00X", "RINOFARINGITIS AGUDA [RESFRIADO COMÚN]", "CIE-10", True),
            ("K297", "GASTRITIS, NO ESPECIFICADA", "CIE-10", False),
        ]:
            CatCies.objects.create(
                code=code, description=description, version=version, is_active=active, created_at=now
            )

    def _login_with(self, permission_codes, username="cies_reader"):
        role = CatRol.objects.create(
            rol=f"ROL_{username.upper()}",
            desc_rol="Rol de prueba del catalogo CIE",
            landing_route="/admin/catalogos",
            is_active=True,
        )
        for code in permission_codes:
            perm = CatPermiso.objects.get_or_create(
                codigo=code, defaults=dict(descripcion=code, is_active=True)
            )[0]
            RelRolPermiso.objects.create(id_rol=role, id_permiso=perm)
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("Cies_123456"),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre="Cies", paterno="Lector", materno="")
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": username, "password": "Cies_123456"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def _codes(self, response):
        return [item["code"] for item in response.data["items"]]

    def test_lista_paginada_ordenada_por_clave_en_camel_case(self):
        response = self.client.get(LIST_URL, {"sortBy": "code"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._codes(response), ["E119", "I10", "J00X", "K297"])
        self.assertEqual(response.data["total"], 4)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(
            response.data["items"][2],
            {"code": "J00X", "name": "RINOFARINGITIS AGUDA [RESFRIADO COMÚN]", "version": "CIE-10", "isActive": True},
        )

    def test_busca_por_descripcion(self):
        response = self.client.get(LIST_URL, {"search": "gastritis"})

        self.assertEqual(self._codes(response), ["K297"])

    def test_busca_por_clave_escrita_con_punto(self):
        response = self.client.get(LIST_URL, {"search": "e11.9"})

        self.assertEqual(self._codes(response), ["E119"])

    def test_filtra_por_version(self):
        response = self.client.get(LIST_URL, {"version": "CIE10", "sortBy": "code"})

        self.assertEqual(self._codes(response), ["I10"])

    def test_filtra_inactivos(self):
        response = self.client.get(LIST_URL, {"isActive": "false"})

        self.assertEqual(self._codes(response), ["K297"])

    def test_sin_permiso_de_lectura_devuelve_403(self):
        self.client.cookies.clear()
        self._login_with(["admin:catalogos:cies:upload"], username="cies_uploader")

        response = self.client.get(LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
