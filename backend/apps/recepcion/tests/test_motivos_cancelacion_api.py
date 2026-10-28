from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import MotivoCita, Permisos, Roles

URL = "/api/v1/citas/motivos-cancelacion"


class MotivosCancelacionApiTests(APITestCase):
    """GET /citas/motivos-cancelacion: catálogo de motivos para los diálogos
    de cancelar cita y ficha (el catálogo admin pide permiso de catálogos)."""

    def _crear_usuario(self, username, permisos):
        user = SyUsuario.objects.create(
            usuario=username, correo=f"{username}@example.com",
            clave_hash=make_password("Clave_123456"), est_activo=True,
            cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, paterno="Test", materno="User")
        rol = Roles.objects.create(rol=f"ROL_{username}", desc_rol="Rol", landing_route="/recepcion")
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=rol, is_primary=True)
        for codigo in permisos:
            permiso, _ = Permisos.objects.get_or_create(codigo=codigo, defaults={"descripcion": codigo, "is_active": True})
            RelRolPermiso.objects.get_or_create(id_rol=rol, id_permiso=permiso)

    def _login(self, username):
        self.client.cookies.clear()
        PolicyStore().clear_active_session(SyUsuario.objects.get(usuario=username).id_usuario)
        response = self.client.post("/api/v1/auth/login", {"username": username, "password": "Clave_123456"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def test_devuelve_solo_motivos_activos_de_cancelacion(self):
        MotivoCita.objects.create(name="Motivo inactivo", aplica_a="CANCELACION", is_active=False)
        self._crear_usuario("agenda_user", ["recepcion:citas:read"])
        self._login("agenda_user")

        response = self.client.get(URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {m["name"] for m in response.data["results"]}
        self.assertIn("Cancelada por el paciente", nombres)
        self.assertIn("Error de captura / duplicado", nombres)  # AMBOS
        self.assertNotIn("Paciente no se presentó", nombres)    # solo NO_ASISTIO
        self.assertNotIn("Motivo inactivo", nombres)
        self.assertEqual(set(response.data["results"][0]), {"id", "name"})

    def test_recepcion_de_fichas_puede_leerlos(self):
        self._crear_usuario("cola_user", ["recepcion:fichas:medicina_general:create"])
        self._login("cola_user")

        response = self.client.get(URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_quien_solo_puede_cancelar_citas_puede_leerlos(self):
        self._crear_usuario("cancela_user", ["recepcion:citas:write"])
        self._login("cancela_user")

        response = self.client.get(URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sin_permiso_de_agenda_ni_cola_responde_403(self):
        self._crear_usuario("otro_user", ["clinico:somatometria:read"])
        self._login("otro_user")

        response = self.client.get(URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
