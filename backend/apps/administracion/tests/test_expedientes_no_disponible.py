"""
Incidente 2026-10-23: con cat_clinicas borrada de la replica, buscar_expediente
devolvia vacio y el expediente aparecia como "no encontrado" (y la vigencia
quedaba sin verificar en silencio). Una falla tecnica ya no se confunde con
un expediente inexistente.
"""
import logging
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.administracion.use_cases.expedientes.buscar_expediente import (
    ExpedientesNoDisponible,
    buscar_expediente,
    buscar_por_nombre,
)
from apps.administracion.views import expediente_view
from apps.recepcion.services import vigencia_service
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case import visit_queue_usecase


class BuscarExpedienteFallaTests(SimpleTestCase):
    # En tests la conexion "expedientes" no existe: es una falla tecnica real.
    def test_falla_de_la_replica_ya_no_devuelve_vacio(self):
        with self.assertRaises(ExpedientesNoDisponible):
            buscar_expediente("40041")
        with self.assertRaises(ExpedientesNoDisponible):
            buscar_por_nombre("PEREZ")

    def test_sin_dato_no_consulta_y_devuelve_vacio(self):
        self.assertEqual(buscar_expediente(""), {"empleados": [], "familiares": []})
        self.assertEqual(buscar_por_nombre("ab"), [])


class LlamadoresTests(SimpleTestCase):
    def test_recepcion_responde_503_y_no_dice_no_encontrado(self):
        with mock.patch.object(visit_queue_usecase, "buscar_expediente", side_effect=ExpedientesNoDisponible("x")):
            with self.assertRaises(VisitDomainError) as error:
                visit_queue_usecase.lookup_patient("40041")
        self.assertEqual(error.exception.code, "EXPEDIENTES_NO_DISPONIBLE")
        self.assertEqual(error.exception.status_code, 503)

    def test_vigencia_no_bloquea_pero_lo_registra_como_error(self):
        with mock.patch.object(vigencia_service, "buscar_expediente", side_effect=ExpedientesNoDisponible("x")), \
             self.assertLogs(vigencia_service.logger, level=logging.ERROR) as logs:
            self.assertTrue(vigencia_service.tiene_vigencia("40041", 0))
        self.assertIn("VIGENCIA NO VERIFICADA", logs.output[0])


class ExpedienteViewNoDisponibleTests(TestCase):
    def _get(self, url):
        from rest_framework.test import APIRequestFactory

        request = APIRequestFactory().get(url)
        with mock.patch.object(expediente_view, "_authorize", return_value=(mock.Mock(), None)):
            vista = (expediente_view.ExpedienteView if "buscar-nombre" not in url
                     else expediente_view.BuscarPorNombreView)
            return vista.as_view()(request)

    def test_expediente_responde_503(self):
        with mock.patch.object(expediente_view, "buscar_expediente", side_effect=ExpedientesNoDisponible("x")):
            response = self._get("/api/v1/expedientes/?id_empleado=40041")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "EXPEDIENTES_NO_DISPONIBLE")

    def test_busqueda_por_nombre_responde_503(self):
        with mock.patch.object(expediente_view, "buscar_por_nombre", side_effect=ExpedientesNoDisponible("x")):
            response = self._get("/api/v1/expedientes/buscar-nombre/?nombre=PEREZ")
        self.assertEqual(response.status_code, 503)
