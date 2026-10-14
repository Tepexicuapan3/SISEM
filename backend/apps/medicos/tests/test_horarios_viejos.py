"""
Horarios viejos: al quitar o cambiar el consultorio del médico, sus horarios
libres se regeneran (los que tienen cita se conservan); un médico no ACTIVO
no tiene horarios listados y al reactivarlo se le generan.
"""

from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.medicos.uses_case.consultorio_usecase import (
    remove_consultorio,
    update_consultorio_asignacion,
)
from apps.medicos.uses_case.medico_usecase import update_medico
from apps.portal_citas.services.slots_service import get_slots_portal
from apps.recepcion.models import CitaMedica, EstatusCita, HorarioDisponible
from apps.recepcion.repositories.citas_repository import CitasRepository

DIA = timezone.localdate() + timedelta(days=10)


class HorariosViejosTests(TestCase):
    def setUp(self):
        centro = CatCentroAtencion.objects.create(
            name="Centro Viejos", code="CT-VIE",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.consultorio = Consultorios.objects.create(
            name="Consultorio Viejo", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        self.otro = Consultorios.objects.create(
            name="Consultorio Nuevo", numero=2, id_turn=turno, id_center=centro, is_active=True,
        )
        usuario = SyUsuario.objects.create(
            usuario="medico.viejos", correo="medico.viejos@example.com",
            clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=usuario, nombre="Dr", paterno="Viejos")
        self.medico = CatMedico.objects.create(id_usuario=usuario)
        self.rmc = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=timezone.localdate() - timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=self.rmc, dia_semana=dia_semana(DIA),
            hora_inicio="09:00", hora_fin="10:00", intervalo_cita_min=20, canal="AMBOS",
        )
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=15)

    def _agendar_9am(self):
        slot = HorarioDisponible.objects.get(fecha=DIA, hora="09:00")
        cita = CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), no_exp="EXP-VIE", pk_num=0,
            medico=self.medico, consultorio=self.consultorio,
            fecha_hora=timezone.make_aware(datetime.combine(DIA, slot.hora)),
            duracion_min=20, servicio_tipo="medicina_general", estatus=EstatusCita.AGENDADA,
        )
        HorarioDisponible.objects.filter(pk=slot.pk).update(disponible=False, cita=cita)

    def test_quitar_el_consultorio_retira_sus_horarios_libres_y_conserva_los_con_cita(self):
        self._agendar_9am()

        remove_consultorio(self.medico.id, self.rmc.id)

        horas = [str(h)[:5] for h in HorarioDisponible.objects.filter(fecha=DIA).values_list("hora", flat=True)]
        self.assertEqual(horas, ["09:00"])
        self.assertIsNotNone(HorarioDisponible.objects.get(fecha=DIA).cita)

    def test_cambiar_el_consultorio_regenera_los_horarios_en_el_nuevo(self):
        update_consultorio_asignacion(self.medico.id, self.rmc.id, {"consultorioId": self.otro.id})

        consultorios = set(
            HorarioDisponible.objects.filter(fecha=DIA).values_list("consultorio_id", flat=True)
        )
        self.assertEqual(consultorios, {self.otro.id})

    def test_medico_no_activo_no_lista_horarios_y_al_reactivarlo_se_generan(self):
        update_medico(self.medico, {"estatusMedico": "BAJA"}, actor_id=1)
        self.assertEqual(get_slots_portal(DIA), [])

        HorarioDisponible.objects.all().delete()
        update_medico(self.medico, {"estatusMedico": "ACTIVO"}, actor_id=1)

        self.assertEqual(len(get_slots_portal(DIA)), 3)
