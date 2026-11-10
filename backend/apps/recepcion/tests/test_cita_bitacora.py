"""
Bitácora de la cita (NOM-024): desde el alta. Antes empezaba en el primer
cambio de estatus y no quedaba quién agendó ni cuándo.
"""

import datetime

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import CitaEstatusLog, CitaMedica, EstatusCita
from apps.recepcion.repositories.citas_repository import NOTA_CITA_AGENDADA, CitasRepository


class AltaEnBitacoraTests(TestCase):
    def setUp(self):
        self.fecha = timezone.localdate() + datetime.timedelta(days=3)
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        centro = CatCentroAtencion.objects.create(
            name="Centro Uno", code="C-1", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.consultorio = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        user = SyUsuario.objects.create(usuario="dr.bitacora", correo="dr@example.com", clave_hash="x")
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

    def _crear(self):
        return CitasRepository.create(
            no_exp="EXP-1", pk_num=0, medico_id=self.medico.id, consultorio_id=self.consultorio.id,
            fecha_hora=timezone.make_aware(datetime.datetime.combine(self.fecha, datetime.time(9, 20))),
            created_by_id=42,
        )

    def test_el_alta_queda_en_la_bitacora_con_quien_agendo(self):
        cita = self._crear()

        log = CitaEstatusLog.objects.get(cita_id=cita["id"])
        self.assertEqual(
            (log.from_status, log.to_status, log.changed_by_id, log.notes),
            (None, EstatusCita.AGENDADA, 42, NOTA_CITA_AGENDADA),
        )

    def test_el_historial_sigue_con_los_cambios_de_estatus(self):
        cita = CitaMedica.objects.get(pk=self._crear()["id"])

        CitasRepository.update_estatus(cita, EstatusCita.CONFIRMADA, changed_by_id=7)

        self.assertEqual(
            list(CitaEstatusLog.objects.filter(cita=cita).order_by("id").values_list("from_status", "to_status")),
            [(None, EstatusCita.AGENDADA), (EstatusCita.AGENDADA, EstatusCita.CONFIRMADA)],
        )
