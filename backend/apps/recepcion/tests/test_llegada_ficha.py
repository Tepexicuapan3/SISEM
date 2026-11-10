"""
Llegada de las fichas automáticas: la ficha que genera la cita espera en la
bandeja hasta que recepción ve al paciente y da "Llegó" (en espera -> en
somatometría, el mismo botón de siempre). En ese momento recibe su número de
ficha y queda el registro de llegada en la bitácora (NOM-024).
"""

import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.models import CatMedico
from apps.recepcion.models import CitaMedica, EstatusCita, Visit, VisitStatusLog
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.tests import test_checkin_manual_api as base
from apps.recepcion.uses_case import materializar_fichas_usecase
from apps.recepcion.uses_case.materializar_fichas_usecase import materializar_ficha
from apps.recepcion.uses_case.visit_queue_usecase import (
    NOTA_LLEGADA,
    change_visit_status,
    create_visit,
)


class LlegadaFichaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        usuario = SyUsuario.objects.create(usuario="dr.llegada", correo="dr@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=usuario, nombre="Ana", paterno="Ruiz")
        self.medico = CatMedico.objects.create(id_usuario=usuario)
        mock.patch.object(materializar_fichas_usecase, "_resolver_paciente", return_value=("PEREZ JUAN", True)).start()
        self.addCleanup(mock.patch.stopall)
        self._n = 0

    def _automatica(self, no_exp="EXP-A"):
        self._n += 1
        cita = CitaMedica.objects.create(
            folio=f"CIT-L{self._n}", patient=paciente_de_llave(no_exp, 0), medico=self.medico,
            estatus=EstatusCita.AGENDADA, servicio_tipo="medicina_general",
            fecha_hora=timezone.now() + datetime.timedelta(hours=1),
        )
        return materializar_ficha(cita)

    def _walk_in(self, no_exp="EXP-W"):
        return create_visit(no_exp=no_exp, pk_num=0)

    def test_la_ficha_automatica_espera_la_llegada(self):
        ficha = self._automatica()

        self.assertTrue(ficha["llegadaPendiente"])
        self.assertIsNone(ficha["llegadaEn"])

    def test_la_ficha_de_recepcion_ya_llego(self):
        ficha = self._walk_in()

        self.assertFalse(ficha["llegadaPendiente"])
        self.assertIsNotNone(ficha["llegadaEn"])

    def _llego(self, visit_id, changed_by_id=None):
        # El botón "Llegó" de la bandeja: en espera -> en somatometría.
        return change_visit_status(visit_id, "en_somatometria", changed_by_id=changed_by_id)

    def test_llego_registra_la_llegada_con_numero_y_bitacora(self):
        ficha = self._automatica()

        llegada = self._llego(ficha["id"], changed_by_id=7)

        self.assertEqual(llegada["status"], "en_somatometria")
        self.assertFalse(llegada["llegadaPendiente"])
        self.assertIsNotNone(llegada["llegadaEn"])
        self.assertIsNotNone(llegada["numFicha"])
        logs = list(VisitStatusLog.objects.filter(visit_id=ficha["id"]).order_by("id").values_list("notes", "to_status"))
        self.assertEqual(logs[1:], [(NOTA_LLEGADA, "en_espera"), (None, "en_somatometria")])
        self.assertEqual(VisitStatusLog.objects.get(visit_id=ficha["id"], notes=NOTA_LLEGADA).changed_by_id, 7)

    def test_llego_en_una_ficha_de_recepcion_no_cambia_su_numero(self):
        ficha = self._walk_in()

        llegada = self._llego(ficha["id"])

        self.assertEqual((llegada["numFicha"], llegada["llegadaEn"]), (ficha["numFicha"], ficha["llegadaEn"]))
        self.assertFalse(VisitStatusLog.objects.filter(visit_id=ficha["id"], notes=NOTA_LLEGADA).exists())

    def test_si_la_transicion_falla_no_queda_la_llegada(self):
        ficha = self._automatica()
        Visit.objects.filter(pk=ficha["id"]).update(status="cancelada")

        with self.assertRaises(VisitDomainError):
            self._llego(ficha["id"])

        visit = Visit.objects.get(pk=ficha["id"])
        self.assertEqual((visit.num_ficha, visit.llegada_en), (None, None))

    def test_el_numero_sigue_el_orden_de_llegada(self):
        primera = self._walk_in("EXP-1")
        automatica = self._automatica("EXP-2")
        segunda = self._walk_in("EXP-3")

        llegada = self._llego(automatica["id"])

        # La automática pendiente no ocupa número: el siguiente es el 2.
        self.assertEqual(
            [primera["numFicha"], segunda["numFicha"], llegada["numFicha"]],
            [primera["numFicha"], primera["numFicha"] + 1, primera["numFicha"] + 2],
        )


class LlegadaFichaApiTests(APITestCase):
    setUp = base.CheckinManualApiTests.setUp
    _create_user_with_role = base.CheckinManualApiTests._create_user_with_role
    _login_as = base.CheckinManualApiTests._login_as
    _csrf_headers = base.CheckinManualApiTests._csrf_headers

    def test_llego_por_la_api_registra_la_llegada(self):
        visit = Visit.objects.create(
            folio="VIS-API", patient=paciente_de_llave(base.PACIENTE_NO_EXP, 0),
            arrival_type=Visit.ArrivalType.APPOINTMENT, appointment_id="CIT-API", status="en_espera",
            fecha_consulta=timezone.localdate(), origen_ficha=Visit.OrigenFicha.AUTOMATICA, centro=self.centro,
        )

        response = self.client.patch(
            f"/api/v1/visits/{visit.pk}/status", {"targetStatus": "en_somatometria"}, format="json",
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertFalse(response.data["llegadaPendiente"])
        self.assertIsNotNone(response.data["numFicha"])
