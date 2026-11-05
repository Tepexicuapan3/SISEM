"""Flujo de punta a punta por la API: llegada -> somatometria -> consulta ->
(autorizacion) -> receta impresa. Plan receta-flujo-impresion, seccion 5.

Cada paso lo hace el rol que lo hace en la operacion, con login real (cookie
JWT + CSRF), igual que el frontend. Lo unico que se simula es el padron del
paciente (``get_patient_header``), que en la operacion viene del legado.
"""

from unittest import mock

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, CatCies, Medicamentos, Permisos, Roles
from apps.consulta_medica.models import PrescriptionAuthorization
from apps.impresion.models import PrintLog

HEADER = "apps.consulta_medica.impresion.common.get_patient_header"
PASSWORD = "Flujo_123456"
NO_EXP = "EXP8801"


def _header():
    return {
        "no_exp": NO_EXP, "pk_num": 0, "paternal_surname": "CHAVEZ", "maternal_surname": "HERNANDEZ",
        "first_name": "MARIA", "full_name": "MARIA CHAVEZ HERNANDEZ", "age": "64",
        "birth_date": "07/07/1959", "sex": "F", "source": "cns_paciente",
    }


class FlujoCitaARecetaTests(APITestCase):
    def setUp(self):
        self.request_id = "88888888-8888-8888-8888-888888888888"
        # Todo el personal trabaja en un centro (sin centro, recepcion da CENTRO_NO_ASIGNADO).
        self.centro = CatCentroAtencion.objects.create(
            name="CUAUHTEMOC", code="DFSTC000123", center_type=CatCentroAtencion.TipoCentro.CLINICA,
            is_active=True, address="AV. CHAPULTEPEC 98", postal_code="06700",
        )
        self._user("recepcion_flujo", "RECEPCION", [
            "recepcion:fichas:medicina_general:read",
            "recepcion:fichas:medicina_general:create",
        ])
        self._user("somato_flujo", "SOMATOMETRIA", ["clinico:somatometria:read"])
        self.doctor = self._user("doctor_flujo", "DOCTOR", ["clinico:recetas:imprimir"])
        self._user("autorizador_flujo", "AUTORIZADOR_RX", ["clinico:recetas:authorize"])

        CatCies.objects.create(code="J00", description="RESFRIADO COMUN", version="CIE-10", is_active=True)
        self.paracetamol = Medicamentos.objects.create(
            name="Paracetamol 500mg", generic_name="Paracetamol",
            cuadro_basico=Medicamentos.CuadroBasico.BASICO, is_controlled=False,
        )
        self.clonazepam = Medicamentos.objects.create(
            name="Clonazepam 2mg", generic_name="Clonazepam",
            cuadro_basico=Medicamentos.CuadroBasico.BASICO, is_controlled=True,
        )

    # -- helpers ---------------------------------------------------------

    def _user(self, username, role_code, permissions):
        user = SyUsuario.objects.create(
            usuario=username, correo=f"{username}@example.com", clave_hash=make_password(PASSWORD),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user, nombre=username, paterno="Test", materno="Flujo", id_centro_atencion=self.centro,
        )
        role, _ = Roles.objects.get_or_create(
            rol=role_code, defaults={"desc_rol": f"Rol {role_code}", "landing_route": "/dashboard"},
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        for code in permissions:
            permission, _ = Permisos.objects.get_or_create(
                codigo=code, defaults={"descripcion": code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        return user

    def _login(self, username):
        self.client.cookies.clear()
        user = SyUsuario.objects.get(usuario=username)
        PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": username, "password": PASSWORD},
            format="json", HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.client.cookies = response.cookies

    def _post(self, url, payload=None, method="post"):
        self.client.cookies["csrf_token"] = "csrf-flujo"
        return getattr(self.client, method)(
            url, payload or {}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, HTTP_X_CSRF_TOKEN="csrf-flujo",
        )

    def _ok(self, response, expected=status.HTTP_200_OK):
        body = getattr(response, "data", None) or response.content[:300]
        self.assertEqual(response.status_code, expected, body)
        return response

    def _print_receta(self, visit_id):
        with mock.patch(HEADER, return_value=_header()):
            return self.client.get(f"/api/v1/impresion/receta/{visit_id}", HTTP_X_REQUEST_ID=self.request_id)

    def _hasta_consulta(self):
        """Recepcion registra la llegada, somatometria captura signos y el
        medico inicia la consulta. Devuelve el id de la visita."""
        self._login("recepcion_flujo")
        visit = self._ok(self._post("/api/v1/visits", {
            "noExp": NO_EXP, "pkNum": 0, "arrivalType": "walk_in", "serviceType": "medicina_general",
        }), status.HTTP_201_CREATED).data
        visit_id = visit["id"]
        self.assertEqual(visit["status"], "en_espera")
        moved = self._ok(self._post(f"/api/v1/visits/{visit_id}/status", {"targetStatus": "en_somatometria"}, method="patch"))
        self.assertEqual(moved.data["status"], "en_somatometria")

        self._login("somato_flujo")
        vitals = self._ok(self._post(f"/api/v1/visits/{visit_id}/vitals", {
            "weightKg": 70, "heightCm": 160, "temperatureC": 36.6, "oxygenSaturationPct": 98,
        }))
        self.assertEqual(vitals.data["status"], "lista_para_doctor")

        self._login("doctor_flujo")
        started = self._ok(self._post(f"/api/v1/visits/{visit_id}/consultation/start"))
        self.assertEqual(started.data["status"], "en_consulta")
        return visit_id

    def _recetar_y_cerrar(self, visit_id, medication):
        diagnosis = {
            "primaryDiagnosis": "Resfriado comun", "finalNote": "Reposo y liquidos.",
            "cieCode": "J00", "morbidity": "1",
        }
        # Sin diagnostico guardado no se pueden agregar medicamentos (CONSULTATION_NOT_FOUND).
        self._ok(self._post(f"/api/v1/visits/{visit_id}/diagnosis", diagnosis))
        self._ok(self._post(f"/api/v1/visits/{visit_id}/prescription-items", {
            "medicationId": medication.id, "quantity": 1, "dose": "1 tab", "indications": "Despues de comer",
            "route": "oral", "frequency": "Cada 8 horas", "duration": "5 dias",
        }), status.HTTP_201_CREATED)
        closed = self._ok(self._post(f"/api/v1/visits/{visit_id}/consultation/close", diagnosis))
        self.assertEqual(closed.data["visit"]["status"], "cerrada")

    def _historial_item(self, visit_id):
        response = self._ok(self.client.get(
            f"/api/v1/patients/{NO_EXP}/consultations", {"pkNum": 0}, HTTP_X_REQUEST_ID=self.request_id,
        ))
        return next(i for i in response.data["items"] if i["visitId"] == visit_id)

    # -- flujos ----------------------------------------------------------

    def test_medicamento_basico_de_la_llegada_a_la_receta_impresa(self):
        visit_id = self._hasta_consulta()
        self._recetar_y_cerrar(visit_id, self.paracetamol)

        # Sin indicaciones libres: el historial igual ofrece imprimir (H1).
        item = self._historial_item(visit_id)
        self.assertEqual(item["prescriptionMedications"], ["Paracetamol 500mg"])
        self.assertEqual(item["prescriptionItems"], [])

        response = self._ok(self._print_receta(visit_id))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response["X-Print-Copy"], "1")

        reprint = self._ok(self._print_receta(visit_id))
        self.assertEqual(reprint["X-Print-Copy"], "2")
        self.assertEqual(PrintLog.objects.filter(documento="receta", resource_id=visit_id).count(), 2)

    def test_controlado_bloquea_la_impresion_hasta_autorizar(self):
        visit_id = self._hasta_consulta()
        self._recetar_y_cerrar(visit_id, self.clonazepam)

        blocked = self._print_receta(visit_id)
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(blocked.json()["code"], "DOCUMENT_NOT_PRINTABLE")

        auth = PrescriptionAuthorization.objects.get(prescription__id_visit_id=visit_id)
        self._login("autorizador_flujo")
        self._ok(self._post(f"/api/v1/prescriptions/authorizations/{auth.id_authorization}/authorize"))

        self._login("doctor_flujo")
        response = self._ok(self._print_receta(visit_id))
        self.assertTrue(response.content.startswith(b"%PDF"))
