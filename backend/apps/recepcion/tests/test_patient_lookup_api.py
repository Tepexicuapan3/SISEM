"""
Tests de contrato para GET /visits/patient-lookup (PatientLookupView).

Cubre el bug real corregido el 2026-09-14: el parametro `historico` de la
query nunca se declaraba en PatientLookupQuerySerializer, asi que DRF lo
ignoraba en silencio y la vista siempre llamaba a lookup_patient() con el
default (historico=False) -- el expediente (que manda historico=true para
ver tambien derechohabientes de baja) nunca recibia lo que pedia. Tambien
cubre que curp/foto (agregados el mismo dia, ver _build_member) lleguen
hasta la respuesta HTTP real, no solo hasta la funcion lookup_patient().

Se mockea `buscar_expediente` -- el alias de BD "expedientes" NO existe
bajo `manage.py test` (mismo motivo documentado en
test_checkin_manual_api.py).
"""

from unittest import mock

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles

PACIENTE_NO_EXP = "40041"

PACIENTE_EXPEDIENTE_MOCK = {
    "empleados": [
        {
            "NO_EXP": PACIENTE_NO_EXP,
            "DS_PATERNO": "HERNANDEZ", "DS_MATERNO": "ROMERO", "DS_NOMBRE": "ANA LAURA",
            "FE_NAC": "1994-08-25", "EDAD": 32,
            "ESTATUS": "ACTIVO", "CD_CLINICA": 2,
            "CURP": "HERA940825MDFRMN03",
            "FOTO": "ZmFrZS1qcGVnLWJhc2U2NA==",
        },
    ],
    "familiares": [
        {
            "NO_EXPF": PACIENTE_NO_EXP, "PK_NUM": 48411,
            "DS_PATERNO": "ROMERO", "DS_MATERNO": "VAZQUEZ", "DS_NOMBRE": "FELIX",
            "FE_NAC": "1990-01-01", "EDAD": 36,
            "CD_PARENTESCO": "ESPOSO (A)", "ESTATUS": "ACTIVO", "CD_CLINICA": 2,
            "CURP": None,
            "FOTO": None,
        },
        {
            "NO_EXPF": PACIENTE_NO_EXP, "PK_NUM": 48412,
            "DS_PATERNO": "ROMERO", "DS_MATERNO": "VAZQUEZ", "DS_NOMBRE": "SOFIA",
            "FE_NAC": "2015-03-10", "EDAD": 11,
            "CD_PARENTESCO": "HIJA (O)", "ESTATUS": "NO ACTIVO", "CD_CLINICA": 2,
            "CURP": "ROVS150310MDFXXX09",
            "FOTO": None,
        },
    ],
}


class PatientLookupApiTests(APITestCase):
    def setUp(self):
        expediente_patcher = mock.patch(
            "apps.recepcion.uses_case.visit_queue_usecase.buscar_expediente",
            return_value=PACIENTE_EXPEDIENTE_MOCK,
        )
        self.addCleanup(expediente_patcher.stop)
        expediente_patcher.start()

        self.request_id = "33333333-3333-3333-3333-333333333333"
        self.password = "Recep_123456"
        # "flow.visits.queue.read" es una capability (ver
        # permission_dependencies.py CAPABILITY_REQUIREMENTS) que exige
        # anyOf + dependencias -- mismo set que ya usa
        # test_checkin_manual_api.py (RECEPCION_CHECKIN) para no derivar
        # el grafo de dependencias a mano.
        self._create_user_with_role(
            username="patient_lookup_user",
            email="patient_lookup@example.com",
            password=self.password,
            role_code="RECEPCION_LOOKUP",
            permissions=[
                "recepcion:citas:read",
                "recepcion:fichas:medicina_general:read",
                "recepcion:fichas:medicina_general:create",
            ],
        )
        self._login_as("patient_lookup_user", self.password)

    def _create_user_with_role(self, username, email, password, role_code, permissions=None):
        user = SyUsuario.objects.create(
            usuario=username, correo=email, clave_hash=make_password(password),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user, nombre=username, paterno="Test", materno="User",
        )
        role = Roles.objects.create(
            rol=role_code, desc_rol=f"Rol {role_code}",
            landing_route="/recepcion", is_admin=False,
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        for permission_code in permissions or []:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code,
                defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": username, "password": password},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def test_default_only_returns_active_members(self):
        """
        Sin `historico`, el bug corregido hacia que esto SIEMPRE se
        comportara asi -- pero ahora es explicito y verificado: el
        familiar "NO ACTIVO" (Sofia) no debe aparecer.
        """
        response = self.client.get(f"/api/v1/visits/patient-lookup?noExp={PACIENTE_NO_EXP}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = [d["nombre"] for d in response.data["dependientes"]]
        self.assertIn("ROMERO VAZQUEZ FELIX", nombres)
        self.assertNotIn("ROMERO VAZQUEZ SOFIA", nombres)

    def test_historico_true_includes_inactive_members(self):
        """
        El fix real: antes de hoy, `historico=true` NO se propagaba a
        lookup_patient() -- este test falla contra el codigo viejo.
        """
        response = self.client.get(
            f"/api/v1/visits/patient-lookup?noExp={PACIENTE_NO_EXP}&historico=true"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = [d["nombre"] for d in response.data["dependientes"]]
        self.assertIn("ROMERO VAZQUEZ FELIX", nombres)
        self.assertIn("ROMERO VAZQUEZ SOFIA", nombres)

    def test_titular_includes_curp_and_photo(self):
        response = self.client.get(
            f"/api/v1/visits/patient-lookup?noExp={PACIENTE_NO_EXP}&historico=true"
        )

        titular = response.data["titular"]
        self.assertEqual(titular["curp"], "HERA940825MDFRMN03")
        self.assertEqual(titular["foto"], "data:image/jpeg;base64,ZmFrZS1qcGVnLWJhc2U2NA==")

    def test_dependiente_sin_curp_ni_foto_queda_en_null(self):
        """
        No se inventa un valor cuando la fuente no lo tiene -- mismo
        criterio que el resto del sistema (nunca adivinar).
        """
        response = self.client.get(
            f"/api/v1/visits/patient-lookup?noExp={PACIENTE_NO_EXP}&historico=true"
        )

        felix = next(
            d for d in response.data["dependientes"] if d["nombre"] == "ROMERO VAZQUEZ FELIX"
        )
        self.assertIsNone(felix["curp"])
        self.assertIsNone(felix["foto"])

    def test_missing_permission_returns_403(self):
        self._create_user_with_role(
            username="sin_permiso_user",
            email="sin_permiso@example.com",
            password="Sin_Permiso123",
            role_code="SIN_PERMISO",
            permissions=[],
        )
        self._login_as("sin_permiso_user", "Sin_Permiso123")

        response = self.client.get(f"/api/v1/visits/patient-lookup?noExp={PACIENTE_NO_EXP}")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
