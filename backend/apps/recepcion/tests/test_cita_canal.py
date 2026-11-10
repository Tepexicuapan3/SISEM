"""
Canal de cada movimiento de la bitácora de la cita (``CitaEstatusLog.canal``):
RECEPCION, MEDICO, PORTAL o SISTEMA. Sin él, un movimiento sin usuario no dice
si fue el paciente desde el portal o una tarea automática.
"""

import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import CanalMovimiento, CitaEstatusLog, CitaMedica, EstatusCita
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.asistencia_cita_service import marcar_atendida
from apps.recepcion.tasks import marcar_no_asistio
from apps.recepcion.uses_case import agendar_cita_usecase, materializar_fichas_usecase
from apps.recepcion.uses_case.cita_historial_usecase import get_cita_historial
from apps.recepcion.uses_case.materializar_fichas_usecase import marcar_fichas_no_llegaron, materializar_ficha
from apps.recepcion.uses_case.visit_queue_usecase import create_visit


class CanalBitacoraTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.fecha = timezone.localdate() + datetime.timedelta(days=3)
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        centro = CatCentroAtencion.objects.create(
            name="Centro Uno", code="C-1", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.consultorio = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        user = SyUsuario.objects.create(usuario="dr.canal", correo="dr@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=user, nombre="Ana", paterno="Ruiz")
        self.medico = CatMedico.objects.create(id_usuario=user)
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=self.fecha - datetime.timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana=dia_semana(self.fecha),
            hora_inicio="09:00", hora_fin="10:00", intervalo_cita_min=20, canal="AMBOS",
        )
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=7)
        mock.patch.object(agendar_cita_usecase, "tiene_vigencia", return_value=True).start()
        mock.patch.object(agendar_cita_usecase, "centro_del_paciente", return_value=None).start()
        mock.patch.object(materializar_fichas_usecase, "_resolver_paciente", return_value=("PEREZ", True)).start()
        mock.patch.object(materializar_fichas_usecase, "publish_visit_created").start()
        mock.patch.object(materializar_fichas_usecase, "publish_visit_no_show").start()
        self.addCleanup(mock.patch.stopall)
        self._n = 0

    def _canales(self, cita):
        return list(CitaEstatusLog.objects.filter(cita_id=cita.id).order_by("id").values_list("to_status", "canal"))

    def _agendar(self, **extra):
        cita = agendar_cita_usecase.agendar_cita(
            no_exp="EXP-1", pk_num=0, medico_id=self.medico.id, consultorio_id=self.consultorio.id,
            fecha_hora=timezone.make_aware(datetime.datetime.combine(self.fecha, datetime.time(9, 20))),
            created_by_id=None, operador=None, request=None, **extra,
        )
        return CitaMedica.objects.get(pk=cita["id"])

    def _cita(self, fecha_hora):
        self._n += 1
        return CitaMedica.objects.create(
            folio=f"CIT-C{self._n}", patient=paciente_de_llave(f"EXP-C{self._n}", 0), medico=self.medico,
            estatus=EstatusCita.AGENDADA, servicio_tipo="medicina_general", fecha_hora=fecha_hora,
        )

    def test_agendar_en_recepcion(self):
        self.assertEqual(self._canales(self._agendar()), [(EstatusCita.AGENDADA, CanalMovimiento.RECEPCION)])

    def test_agendar_desde_la_consulta(self):
        cita = self._agendar(canal=CanalMovimiento.MEDICO)
        self.assertEqual(self._canales(cita), [(EstatusCita.AGENDADA, CanalMovimiento.MEDICO)])

    def test_atendida_al_cerrar_la_consulta(self):
        cita = self._agendar()
        marcar_atendida(cita.folio, changed_by_id=None)
        self.assertEqual(self._canales(cita)[-1], (EstatusCita.ATENDIDA, CanalMovimiento.MEDICO))

    def test_check_in_de_recepcion(self):
        cita = self._cita(timezone.now() + datetime.timedelta(hours=1))
        create_visit(no_exp=cita.patient.no_exp, pk_num=0, arrival_type="appointment", appointment_id=cita.folio)
        self.assertEqual(self._canales(cita), [(EstatusCita.CONFIRMADA, CanalMovimiento.RECEPCION)])

    def test_ficha_automatica_y_no_llego_son_del_sistema(self):
        cita = self._cita(timezone.now() - datetime.timedelta(hours=3))
        materializar_ficha(cita)
        marcar_fichas_no_llegaron()
        self.assertEqual(
            self._canales(cita),
            [(EstatusCita.CONFIRMADA, CanalMovimiento.SISTEMA), (EstatusCita.NO_ASISTIO, CanalMovimiento.SISTEMA)],
        )

    def test_no_asistio_sin_check_in_es_del_sistema(self):
        cita = self._cita(timezone.now() - datetime.timedelta(minutes=10))
        marcar_no_asistio()
        self.assertEqual(self._canales(cita), [(EstatusCita.NO_ASISTIO, CanalMovimiento.SISTEMA)])

    def test_el_historial_trae_el_canal(self):
        cita = self._agendar()
        self.assertEqual(get_cita_historial(cita)[0]["canal"], CanalMovimiento.RECEPCION)
