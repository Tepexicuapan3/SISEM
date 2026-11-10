"""
``GET /citas/{id}/historial``: la bitácora NOM-024 de la cita (alta y cambios
de estatus) con el nombre de quien hizo cada movimiento. Mismo setUp de login
real que ``test_checkin_manual_api``.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion
from apps.recepcion.models import CitaEstatusLog, EstatusCita
# Por módulo: importar la clase al namespace haría que se corran sus tests acá.
from apps.recepcion.tests import test_checkin_manual_api as base


class CitaHistorialApiTests(APITestCase):
    setUp = base.CheckinManualApiTests.setUp
    _create_user_with_role = base.CheckinManualApiTests._create_user_with_role
    _login_as = base.CheckinManualApiTests._login_as
    _cita_hoy = base.CheckinManualApiTests._cita_hoy

    def _get(self, cita):
        return self.client.get(f"/api/v1/citas/{cita.id}/historial")

    def test_lista_los_movimientos_en_orden_con_el_nombre(self):
        cita = self._cita_hoy()
        operador = SyUsuario.objects.create(usuario="op.hist", correo="op@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=operador, nombre="Rosa", paterno="Mora")
        CitaEstatusLog.objects.create(cita=cita, to_status=EstatusCita.AGENDADA, changed_by_id=operador.id_usuario,
                                      notes="Cita agendada")
        CitaEstatusLog.objects.create(cita=cita, from_status=EstatusCita.AGENDADA, to_status=EstatusCita.CANCELADA,
                                      notes="Paciente lo solicitó")

        response = self._get(cita)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.json()["items"]
        self.assertEqual([(i["fromStatus"], i["toStatus"]) for i in items],
                         [(None, "agendada"), ("agendada", "cancelada")])
        self.assertIn("Rosa", items[0]["changedByNombre"])
        self.assertEqual(items[1]["notes"], "Paciente lo solicitó")
        self.assertIsNone(items[1]["changedByNombre"])

    def test_cita_de_otro_centro_no_existe(self):
        otro = CatCentroAtencion.objects.create(
            name="Otro", code="CT-OTRO", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        cita = self._cita_hoy(centro=otro)

        self.assertEqual(self._get(cita).status_code, status.HTTP_404_NOT_FOUND)
