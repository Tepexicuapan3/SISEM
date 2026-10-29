"""
Cita de seguimiento desde la nota (P-12): el médico elige un horario libre
de SU agenda y la cita se crea al cerrar la nota, en la misma transacción.
Si el horario ya no se puede usar, la nota no se cierra.
"""

import datetime

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, CatCies, Consultorios, Turnos
from apps.consulta_medica.uses_case.consultation_usecase import close_consultation
from apps.consulta_medica.uses_case.follow_up_usecase import MOTIVO_SEGUIMIENTO, list_follow_up_slots
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import CitaMedica, HorarioDisponible, Visit
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


def _noop_audit_hook(**kwargs):
    return None


class CitaSeguimientoTests(TestCase):
    def setUp(self):
        CatCies.objects.create(code="I10", description="HIPERTENSION ESENCIAL", version="CIE-10", is_active=True)
        self.today = timezone.localdate()
        self.seguimiento = self.today + datetime.timedelta(days=14)

        centro = CatCentroAtencion.objects.create(
            name="Centro Seguimiento", code="CT-SEG",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.consultorio = Consultorios.objects.create(
            name="Consultorio Seguimiento", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        self.doctor_id, self.medico = self._medico("doctor.seguimiento")
        _, self.otro_medico = self._medico("otro.medico")

    def _medico(self, usuario):
        user = SyUsuario.objects.create(usuario=usuario, correo=f"{usuario}@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=user, nombre="Dr", paterno=usuario)
        medico = CatMedico.objects.create(id_usuario=user)
        rel = RelMedicoConsultorio.objects.create(
            medico=medico, consultorio=self.consultorio,
            fecha_inicio=self.today - datetime.timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana=dia_semana(self.seguimiento),
            hora_inicio="09:00", hora_fin="10:00", intervalo_cita_min=20, canal="AMBOS",
        )
        CitasRepository.generar_slots_medico(medico_id=medico.id, dias_adelante=20)
        return user.id_usuario, medico

    def _visit(self):
        n = Visit.objects.count() + 1
        return Visit.objects.create(
            folio=f"SEG-{n}", patient=_paciente_de_llave("EXP-SEG", 0), arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-SEG-{n}", status="en_consulta", fecha_consulta=self.today,
        )

    def _slot(self, medico, hora="09:20"):
        return HorarioDisponible.objects.get(medico=medico, fecha=self.seguimiento, hora=hora)

    def _close(self, visit, **extra):
        return close_consultation(
            visit_id=visit.id_visit, roles=["DOCTOR"], primary_diagnosis="Hipertension",
            final_note="Control", doctor_id=self.doctor_id, cie_code="I10",
            audit_hook=_noop_audit_hook, morbidity="2", follow_up_date=self.seguimiento, **extra,
        )

    def test_lista_solo_los_horarios_libres_del_medico(self):
        HorarioDisponible.objects.filter(medico=self.medico, hora="09:40").update(canal="LINEA")

        horas = [s["hora"] for s in list_follow_up_slots(self.seguimiento, self.doctor_id)]

        self.assertEqual(horas, ["09:00", "09:20"])

    def test_cerrar_con_horario_crea_la_cita_de_seguimiento(self):
        visit = self._visit()
        slot = self._slot(self.medico)

        payload = self._close(visit, follow_up_slot_id=slot.id)

        cita = CitaMedica.objects.get()
        # Plan contraer la llave vieja: la cita guarda solo el paciente de la visita.
        self.assertEqual(cita.patient_id, visit.patient_id)
        self.assertEqual((cita.patient.no_exp, cita.medico_id, cita.motivo), ("EXP-SEG", self.medico.id, MOTIVO_SEGUIMIENTO))
        self.assertEqual(cita.notas, f"Consulta {visit.folio}")
        self.assertEqual(payload["followUpAppointment"]["folio"], cita.folio)
        slot.refresh_from_db()
        self.assertEqual(slot.cita, cita)

    def test_sin_horario_solo_queda_la_fecha(self):
        payload = self._close(self._visit())

        self.assertIsNone(payload["followUpAppointment"])
        self.assertFalse(CitaMedica.objects.exists())

    def test_horario_de_otro_medico_se_rechaza_y_la_nota_no_se_cierra(self):
        visit = self._visit()

        with self.assertRaises(VisitDomainError) as raised:
            self._close(visit, follow_up_slot_id=self._slot(self.otro_medico).id)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("followUpSlotId", raised.exception.details)
        visit.refresh_from_db()
        self.assertEqual(visit.status, "en_consulta")

    def test_horario_ocupado_revierte_el_cierre(self):
        visit = self._visit()
        slot = self._slot(self.medico)
        HorarioDisponible.objects.filter(pk=slot.pk).update(disponible=False)

        with self.assertRaises(VisitDomainError) as raised:
            self._close(visit, follow_up_slot_id=slot.id)

        self.assertEqual(raised.exception.code, "FOLLOW_UP_SLOT_UNAVAILABLE")
        visit.refresh_from_db()
        self.assertEqual(visit.status, "en_consulta")
        self.assertFalse(CitaMedica.objects.exists())

    def test_horario_de_otra_fecha_se_rechaza(self):
        otro_dia = HorarioDisponible.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha=self.seguimiento + datetime.timedelta(days=1), hora="11:00",
        )

        with self.assertRaises(VisitDomainError) as raised:
            self._close(self._visit(), follow_up_slot_id=otro_dia.id)

        self.assertIn("followUpSlotId", raised.exception.details)
