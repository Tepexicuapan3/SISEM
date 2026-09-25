"""
Change `incapacidad-medica-recepcion-frontend`: GET
patients/<no_exp>/medical-leaves ahora acepta el permiso de solo lectura
`recepcion:incapacidad:read` ademas de DOCTOR/clinico:consultas:read, pero
POST visits/<id>/medical-leave (crear) sigue siendo EXCLUSIVO del medico.

Ver `ensure_doctor_or_incapacidad_read_role` en
`apps/consulta_medica/uses_case/consultation_usecase.py` -- el guard nuevo
NO reemplaza a `ensure_doctor_role`, que sigue protegiendo la creacion.
"""
from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Licencias, Permisos, Roles
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis
from apps.recepcion.models import Visit


def _noop_audit_hook(**kwargs):
    """Setup-only: arma el estado previo (consulta) sin generar el evento
    de auditoria bajo prueba -- mismo criterio que en el resto de la suite
    de consulta_medica."""
    return None


class MedicalLeaveAccessApiTests(APITestCase):
    def setUp(self):
        self.request_id = "88888888-8888-8888-8888-888888888888"
        self.doctor_password = "Doctor_Incap_123456"
        self.recepcion_password = "Recepcion_Incap_123456"

        self.doctor_user = self._create_user_with_role(
            username="incap_doctor",
            email="incap.doctor@example.com",
            password=self.doctor_password,
            role_code="DOCTOR",
        )
        self.recepcion_user = self._create_user_with_role(
            username="incap_recepcion",
            email="incap.recepcion@example.com",
            password=self.recepcion_password,
            role_code="RECEPCION_INCAP",
            permissions=["recepcion:incapacidad:read"],
        )

        self.leave_type = Licencias.objects.create(name="Enfermedad general")

        self.visit = Visit.objects.create(
            folio="VIS-INCAP-001",
            no_exp="EXP-INCAP-001",
            nombre_paciente="Paciente Incapacidad",
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="en_consulta",
        )
        # Arma la consulta previa que create_medical_leave exige
        # (CONSULTATION_NOT_FOUND si no existe), sin pasar por el guard de
        # ensure_doctor_role via API -- llamada directa al usecase, como
        # `_visit_with_consultation` en test_consultation_audit_api.py.
        save_diagnosis(
            self.visit.id_visit, ["DOCTOR"], "Dx previo", "Nota previa",
            doctor_id=self.doctor_user.id_usuario, audit_hook=_noop_audit_hook,
        )

    def _create_user_with_role(self, username, email, password, role_code, permissions=None):
        user = SyUsuario.objects.create(
            usuario=username, correo=email, clave_hash=make_password(password),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, paterno="Test", materno="User")
        role, _ = Roles.objects.get_or_create(
            rol=role_code,
            defaults={"desc_rol": f"Rol {role_code}", "landing_route": "/recepcion/incapacidad"},
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        for permission_code in permissions or []:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code, defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": username, "password": password},
            format="json", HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def _csrf_headers(self):
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _post_medical_leave(self):
        return self.client.post(
            f"/api/v1/visits/{self.visit.id_visit}/medical-leave",
            {
                "leaveTypeId": self.leave_type.id, "days": 3,
                "startDate": "2026-02-01", "isSubsequent": False,
            },
            format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def test_get_medical_leaves_with_incapacidad_read_permission_succeeds(self):
        """Recepcion con SOLO `recepcion:incapacidad:read` (sin rol DOCTOR
        ni clinico:consultas:read) puede consultar el historial -- este es
        el hallazgo bloqueante que motivo el permiso nuevo."""
        self._login_as("incap_recepcion", self.recepcion_password)

        response = self.client.get(
            f"/api/v1/patients/{self.visit.no_exp}/medical-leaves"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 0)

    def test_post_medical_leave_with_incapacidad_read_permission_is_forbidden(self):
        """El mismo usuario de Recepcion NO puede crear una incapacidad --
        `recepcion:incapacidad:read` es de solo lectura, create_medical_leave
        sigue exclusivo de ensure_doctor_role."""
        self._login_as("incap_recepcion", self.recepcion_password)

        response = self._post_medical_leave()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")

    def test_doctor_can_still_create_and_read_medical_leaves(self):
        """Regresion: el medico sigue pudiendo crear Y consultar -- el
        guard nuevo no debe romper el camino existente."""
        self._login_as("incap_doctor", self.doctor_password)

        create_response = self._post_medical_leave()
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        get_response = self.client.get(
            f"/api/v1/patients/{self.visit.no_exp}/medical-leaves"
        )
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_response.data["total"], 1)

    def test_get_medical_leaves_without_any_permission_is_forbidden(self):
        """Baseline: sin DOCTOR/clinico:consultas:read/recepcion:incapacidad:read
        el GET sigue bloqueado -- el anyOf no abre la puerta a cualquiera."""
        self._create_user_with_role(
            username="incap_sin_permiso",
            email="incap.sinpermiso@example.com",
            password="SinPermiso_123456",
            role_code="SIN_PERMISO_INCAP",
            permissions=[],
        )
        self._login_as("incap_sin_permiso", "SinPermiso_123456")

        response = self.client.get(
            f"/api/v1/patients/{self.visit.no_exp}/medical-leaves"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")
