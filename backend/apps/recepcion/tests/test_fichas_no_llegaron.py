"""
No asistió de las fichas automáticas: la que sigue "Por llegar" pasada la hora
de la cita más ``citas.tolerancia_no_show_min`` (60 por omisión) pasa a no
asistió, y su cita también. Así no se queda en la bandeja ni bloquea las
fichas siguientes del paciente.
"""

import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.models import CatMedico
from apps.recepcion.models import CitaMedica, EstatusCita, Visit, VisitStatusLog
from apps.recepcion.uses_case import materializar_fichas_usecase as caso
from apps.recepcion.uses_case.materializar_fichas_usecase import marcar_fichas_no_llegaron, materializar_ficha
from apps.recepcion.uses_case.visit_queue_usecase import change_visit_status, create_visit


class FichasNoLlegaronTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        usuario = SyUsuario.objects.create(usuario="dr.nollego", correo="dr@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=usuario, nombre="Ana", paterno="Ruiz")
        self.medico = CatMedico.objects.create(id_usuario=usuario)
        mock.patch.object(caso, "_resolver_paciente", return_value=("PEREZ JUAN", True)).start()
        self.publicar = mock.patch.object(caso, "publish_visit_no_show").start()
        mock.patch.object(caso, "publish_visit_created").start()
        self.addCleanup(mock.patch.stopall)
        # La cita es a las 10:00 de hoy; "ahora" se pasa a cada corrida.
        self.cita_a_las = timezone.make_aware(datetime.datetime.combine(timezone.localdate(), datetime.time(10, 0)))
        self._n = 0

    def _automatica(self, fecha_hora=None, no_exp="EXP-N"):
        self._n += 1
        cita = CitaMedica.objects.create(
            folio=f"CIT-N{self._n}", patient=paciente_de_llave(no_exp, 0), medico=self.medico,
            estatus=EstatusCita.AGENDADA, servicio_tipo="medicina_general",
            fecha_hora=fecha_hora or self.cita_a_las,
        )
        return cita, materializar_ficha(cita)

    def _a_las(self, minutos_despues):
        return marcar_fichas_no_llegaron(ahora=self.cita_a_las + datetime.timedelta(minutes=minutos_despues))

    def test_pasada_la_tolerancia_la_ficha_y_la_cita_no_asistieron(self):
        cita, ficha = self._automatica()

        with self.captureOnCommitCallbacks(execute=True):
            resumen = self._a_las(61)

        self.assertEqual(resumen["marcadas"], 1)
        visit = Visit.objects.get(pk=ficha["id"])
        self.assertEqual(visit.status, "no_show")
        self.assertTrue(VisitStatusLog.objects.filter(visit=visit, to_status="no_show").exists())
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.NO_ASISTIO)
        self.assertEqual(cita.motivo_cancelacion.name, "Paciente no se presentó")
        self.assertIn("60 min", cita.motivo_detalle)
        self.assertEqual(self.publicar.call_args.kwargs["visit_id"], ficha["id"])

    def test_dentro_de_la_tolerancia_sigue_esperando(self):
        _, ficha = self._automatica()

        self.assertEqual(self._a_las(60)["marcadas"], 0)
        self.assertEqual(Visit.objects.get(pk=ficha["id"]).status, "en_espera")

    def test_la_tolerancia_sale_del_parametro(self):
        self._automatica()

        with mock.patch.object(caso, "tolerancia_no_show", return_value=datetime.timedelta(minutes=15)):
            self.assertEqual(self._a_las(16)["marcadas"], 1)

    def test_no_toca_a_quien_llego(self):
        _, ficha = self._automatica()
        change_visit_status(ficha["id"], "en_somatometria")

        self.assertEqual(self._a_las(120)["marcadas"], 0)
        self.assertEqual(Visit.objects.get(pk=ficha["id"]).status, "en_somatometria")

    def test_no_toca_las_fichas_de_recepcion(self):
        walk_in = create_visit(no_exp="EXP-W", pk_num=0)
        Visit.objects.filter(pk=walk_in["id"]).update(
            fecha_consulta=timezone.localdate(), hora_consulta=datetime.time(8, 0),
        )

        self.assertEqual(self._a_las(600)["marcadas"], 0)
        self.assertEqual(Visit.objects.get(pk=walk_in["id"]).status, "en_espera")

    def test_la_de_ayer_que_quedo_esperando_tambien(self):
        ayer = self.cita_a_las - datetime.timedelta(days=1)
        _, ficha = self._automatica(fecha_hora=ayer)

        self.assertEqual(self._a_las(0)["marcadas"], 1)
        self.assertEqual(Visit.objects.get(pk=ficha["id"]).status, "no_show")

    def test_despues_el_paciente_puede_tener_otra_ficha(self):
        self._automatica(no_exp="EXP-OTRA")
        self._a_las(61)

        self.assertEqual(create_visit(no_exp="EXP-OTRA", pk_num=0)["status"], "en_espera")

    def test_la_tarea_marca_las_que_no_llegaron(self):
        from apps.recepcion.tasks import marcar_fichas_no_llegaron as tarea

        self._automatica(fecha_hora=timezone.now() - datetime.timedelta(hours=3))

        self.assertEqual(tarea()["marcadas"], 1)

    def test_el_comando_tambien_marca_las_que_no_llegaron(self):
        from io import StringIO

        from django.core.management import call_command

        self._automatica(fecha_hora=timezone.now() - datetime.timedelta(hours=3))
        salida = StringIO()

        call_command("materializar_fichas", stdout=salida)

        self.assertIn("No llegaron: 1", salida.getvalue())
