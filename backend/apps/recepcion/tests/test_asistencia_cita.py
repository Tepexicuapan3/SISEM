"""
Asistencia a la cita: el paciente se presenta con la anticipación de
citas.anticipacion_checkin_min; si no, la tarea la deja en no_asistio. Al
cerrar la consulta de su ficha, la cita queda atendida.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import SyUsuario
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.models import CatMedico
from apps.recepcion.models import CitaMedica, EstatusCita, Visit
from apps.recepcion.repositories.citas_repository import TopeCitaExcedido, validar_topes_cita
from apps.recepcion.services.asistencia_cita_service import marcar_atendida
from apps.recepcion.tasks import marcar_no_asistio

NO_EXP = "70700"


class AsistenciaCitaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        usuario = SyUsuario.objects.create(
            usuario="medico_asistencia", correo="medico_asistencia@example.com",
            clave_hash=make_password("x"), est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        self.medico = CatMedico.objects.create(id_usuario=usuario)
        self.ahora = timezone.now().replace(second=0, microsecond=0)
        patcher = mock.patch(
            "apps.recepcion.services.asistencia_cita_service._minuto_actual", return_value=self.ahora,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _cita(self, minutos, pk_num=0, **extra):
        datos = dict(
            folio=CitaMedica.generar_folio(),
            patient=paciente_de_llave(NO_EXP, pk_num),
            medico_id=self.medico.id,
            fecha_hora=self.ahora + timedelta(minutes=minutos), duracion_min=20,
            servicio_tipo="medicina_general", estatus=EstatusCita.AGENDADA,
            motivo="Prueba asistencia",
        )
        datos.update(extra)
        return CitaMedica.objects.create(**datos)

    def test_la_tarea_marca_no_asistio_pasado_el_limite(self):
        tarde = self._cita(29)
        a_tiempo = self._cita(30, pk_num=1)

        marcar_no_asistio()

        tarde.refresh_from_db()
        a_tiempo.refresh_from_db()
        self.assertEqual(tarde.estatus, EstatusCita.NO_ASISTIO)
        self.assertEqual(a_tiempo.estatus, EstatusCita.AGENDADA)

    def test_la_tarea_no_toca_a_quien_hizo_checkin(self):
        verificada = self._cita(-10, verificado_en=timezone.now())
        con_ficha = self._cita(-10, pk_num=1)
        Visit.objects.create(patient=paciente_de_llave(NO_EXP, 1), appointment_id=con_ficha.folio,
                             arrival_type=Visit.ArrivalType.APPOINTMENT)

        marcar_no_asistio()

        verificada.refresh_from_db()
        con_ficha.refresh_from_db()
        self.assertEqual(verificada.estatus, EstatusCita.AGENDADA)
        self.assertEqual(con_ficha.estatus, EstatusCita.AGENDADA)

    def test_cerrar_la_consulta_deja_la_cita_atendida(self):
        cita = self._cita(60, estatus=EstatusCita.CONFIRMADA)

        marcar_atendida(cita.folio, changed_by_id=None)

        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.ATENDIDA)

    def test_no_se_agenda_una_cita_a_la_que_ya_no_llega(self):
        with self.assertRaises(TopeCitaExcedido) as ctx:
            validar_topes_cita(NO_EXP, 0, self.ahora + timedelta(minutes=20))
        self.assertEqual(ctx.exception.code, "CITA_SIN_TIEMPO_CHECKIN")

        validar_topes_cita(NO_EXP, 0, self.ahora + timedelta(minutes=30))
