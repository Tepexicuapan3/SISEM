"""
Reprogramar una cita: se cancela la anterior ("Reagendada") y se agenda la
nueva con las mismas reglas que ``agendar_cita``, en una sola transacción. La
nueva queda enlazada a la anterior (``reprogramada_de``).
"""

import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import CanalMovimiento, CitaEstatusLog, CitaMedica, EstatusCita, HorarioDisponible, Visit
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case import agendar_cita_usecase
from apps.recepcion.uses_case.reprogramar_cita_usecase import reprogramar_cita


class ReprogramarCitaTests(TestCase):
    def setUp(self):
        self.fecha = timezone.localdate() + datetime.timedelta(days=3)
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        centro = CatCentroAtencion.objects.create(
            name="Centro Uno", code="C-1", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.consultorio = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        user = SyUsuario.objects.create(usuario="dr.reprog", correo="dr@example.com", clave_hash="x")
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
        self.addCleanup(mock.patch.stopall)
        self.anterior = self._agendar("09:00")

    def _a_las(self, hora):
        h, m = map(int, hora.split(":"))
        return timezone.make_aware(datetime.datetime.combine(self.fecha, datetime.time(h, m)))

    def _agendar(self, hora):
        cita = agendar_cita_usecase.agendar_cita(
            no_exp="EXP-1", pk_num=0, medico_id=self.medico.id, consultorio_id=self.consultorio.id,
            fecha_hora=self._a_las(hora), motivo="Control", created_by_id=None, operador=None, request=None,
        )
        return CitaMedica.objects.get(pk=cita["id"])

    def _reprogramar(self, hora, **extra):
        return reprogramar_cita(
            cita_id=self.anterior.id, fecha_hora=self._a_las(hora), created_by_id=9, operador=None, request=None,
            **extra,
        )

    def test_cancela_la_anterior_y_agenda_la_nueva_enlazada(self):
        nueva = CitaMedica.objects.get(pk=self._reprogramar("09:40")["id"])

        self.anterior.refresh_from_db()
        self.assertEqual(self.anterior.estatus, EstatusCita.CANCELADA)
        self.assertEqual(self.anterior.motivo_cancelacion.name, "Reagendada")
        self.assertEqual(nueva.reprogramada_de, self.anterior)
        self.assertEqual((nueva.estatus, nueva.motivo, nueva.medico_id), (EstatusCita.AGENDADA, "Control", self.medico.id))
        # El horario de la anterior queda libre; el nuevo, ocupado.
        self.assertTrue(HorarioDisponible.objects.get(medico=self.medico, fecha=self.fecha, hora="09:00").disponible)
        self.assertEqual(HorarioDisponible.objects.get(medico=self.medico, fecha=self.fecha, hora="09:40").cita, nueva)

    def test_la_bitacora_enlaza_las_dos(self):
        nueva = self._reprogramar("09:40")

        cancelacion = CitaEstatusLog.objects.filter(cita=self.anterior).order_by("id").last()
        alta = CitaEstatusLog.objects.get(cita_id=nueva["id"])
        self.assertEqual((cancelacion.to_status, cancelacion.changed_by_id), (EstatusCita.CANCELADA, 9))
        self.assertIn("Reprogramada", cancelacion.notes)
        self.assertEqual(alta.notes, f"Reprogramada desde {self.anterior.folio}")
        self.assertEqual({cancelacion.canal, alta.canal}, {CanalMovimiento.RECEPCION})

    def test_puede_quedar_en_el_mismo_horario_con_otro_motivo(self):
        # Cancelar primero libera el horario, así que el mismo horario sirve.
        nueva = self._reprogramar("09:00")
        self.assertEqual(CitaMedica.objects.get(pk=nueva["id"]).reprogramada_de_id, self.anterior.id)

    def test_si_la_nueva_no_se_puede_la_anterior_queda_igual(self):
        HorarioDisponible.objects.filter(medico=self.medico, fecha=self.fecha, hora="09:40").update(disponible=False)

        with self.assertRaises(VisitDomainError):
            self._reprogramar("09:40")

        self.anterior.refresh_from_db()
        self.assertEqual(self.anterior.estatus, EstatusCita.AGENDADA)
        self.assertFalse(CitaMedica.objects.filter(reprogramada_de=self.anterior).exists())
        self.assertFalse(HorarioDisponible.objects.get(medico=self.medico, fecha=self.fecha, hora="09:00").disponible)

    def test_no_se_reprograma_una_cancelada(self):
        CitasRepository.update_estatus(
            self.anterior, EstatusCita.CANCELADA,
            motivo_cancelacion=CitaMedica._meta.get_field("motivo_cancelacion").related_model.objects.first(),
        )

        with self.assertRaises(VisitDomainError) as raised:
            self._reprogramar("09:40")

        self.assertEqual((raised.exception.code, raised.exception.status_code), ("CITA_NO_REPROGRAMABLE", 409))

    def test_no_se_reprograma_una_cita_con_ficha(self):
        Visit.objects.create(
            folio="VIS-REP", patient=self.anterior.patient, arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=self.anterior.folio, status="en_espera", fecha_consulta=self.fecha,
        )

        with self.assertRaises(VisitDomainError) as raised:
            self._reprogramar("09:40")

        self.assertEqual(raised.exception.code, "CITA_CON_FICHA")
