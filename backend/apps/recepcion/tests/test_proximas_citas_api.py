"""
Contrato de ``GET /citas/proximas`` (Próximas citas de recepción). Mismo
setUp de login real que ``test_checkin_manual_api``.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.recepcion.models import MOTIVO_CITA_SEGUIMIENTO
# Por módulo: importar la clase al namespace haría que se corran sus tests acá.
from apps.recepcion.tests import test_checkin_manual_api as base

PACIENTE_NOMBRE_ESPERADO = base.PACIENTE_NOMBRE_ESPERADO


class ProximasCitasApiTests(APITestCase):
    # Se reutiliza el setUp y los helpers sin heredar (ni repetir) sus tests.
    setUp = base.CheckinManualApiTests.setUp
    _create_user_with_role = base.CheckinManualApiTests._create_user_with_role
    _login_as = base.CheckinManualApiTests._login_as
    _cita_hoy = base.CheckinManualApiTests._cita_hoy

    def _get(self, **params):
        return self.client.get("/api/v1/citas/proximas", params, HTTP_X_REQUEST_ID=self.request_id)

    def test_lista_las_proximas_con_nombre_y_marca_de_seguimiento(self):
        manana = timezone.localtime(timezone.now()) + timedelta(days=1)
        cita = self._cita_hoy(fecha_hora=manana, motivo=MOTIVO_CITA_SEGUIMIENTO)

        response = self._get()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.json()["items"][0]
        self.assertEqual(item["folio"], cita.folio)
        self.assertEqual(item["pacienteNombre"], PACIENTE_NOMBRE_ESPERADO)
        self.assertTrue(item["esSeguimiento"])

    def test_rango_mayor_a_31_dias_devuelve_422(self):
        hoy = timezone.localdate()
        response = self._get(fechaDesde=hoy.isoformat(), fechaHasta=(hoy + timedelta(days=40)).isoformat())
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
