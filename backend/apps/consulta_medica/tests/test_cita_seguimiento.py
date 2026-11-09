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
from apps.consulta_medica.uses_case.follow_up_usecase import (
    MOTIVO_SEGUIMIENTO,
    doctor_has_agenda,
    list_follow_up_days,
    list_follow_up_slots,
    next_follow_up_day,
)
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

    def test_lista_los_horarios_del_dia_con_su_estado(self):
        HorarioDisponible.objects.filter(medico=self.medico, hora="09:40").update(canal="LINEA")
        HorarioDisponible.objects.filter(medico=self.medico, fecha=self.seguimiento, hora="09:20").update(disponible=False)

        slots = list_follow_up_slots(self.seguimiento, self.doctor_id)

        # Los del portal (LINEA) no se muestran; los ocupados sí, marcados.
        self.assertEqual([(s["hora"], s["disponible"]) for s in slots], [("09:00", True), ("09:20", False)])

    def test_dias_con_libres_y_total_del_medico(self):
        HorarioDisponible.objects.filter(medico=self.medico, hora="09:40").update(canal="LINEA")
        HorarioDisponible.objects.filter(medico=self.medico, hora="09:00").update(disponible=False)

        dias = list_follow_up_days(self.today, self.today + datetime.timedelta(days=20), self.doctor_id)

        # El horario semanal solo cae el día de seguimiento (y una semana antes/después).
        por_fecha = {d["fecha"]: (d["libres"], d["total"]) for d in dias}
        self.assertEqual(por_fecha[self.seguimiento.isoformat()], (1, 2))

    def test_dia_lleno_aparece_con_cero_libres(self):
        HorarioDisponible.objects.filter(medico=self.medico, fecha=self.seguimiento).update(disponible=False)

        dias = list_follow_up_days(self.seguimiento, self.seguimiento, self.doctor_id)

        self.assertEqual(dias, [{"fecha": self.seguimiento.isoformat(), "libres": 0, "total": 3}])

    def test_dias_sin_medico_es_lista_vacia(self):
        self.assertEqual(list_follow_up_days(self.today, self.seguimiento, doctor_id=999999), [])

    def test_proximo_dia_libre_desde_una_fecha(self):
        # El horario semanal solo cae el mismo día de la semana que el seguimiento.
        desde = self.seguimiento - datetime.timedelta(days=2)
        self.assertEqual(next_follow_up_day(desde, self.doctor_id), self.seguimiento)

    def test_proximo_dia_salta_los_dias_llenos(self):
        semana_antes = self.seguimiento - datetime.timedelta(days=7)
        HorarioDisponible.objects.filter(medico=self.medico, fecha=semana_antes).update(disponible=False)
        self.assertEqual(next_follow_up_day(semana_antes, self.doctor_id), self.seguimiento)

    def test_proximo_dia_sin_agenda_es_none(self):
        self.assertIsNone(next_follow_up_day(self.today, doctor_id=999999))

    def test_tiene_agenda_solo_si_es_medico_con_horarios(self):
        self.assertTrue(doctor_has_agenda(self.doctor_id))
        self.assertFalse(doctor_has_agenda(999999))
        HorarioDisponible.objects.filter(medico=self.medico).delete()
        self.assertFalse(doctor_has_agenda(self.doctor_id))

    def test_la_cita_del_medico_aparece_en_la_agenda_de_recepcion(self):
        self._close(self._visit(), follow_up_slot_id=self._slot(self.medico).id)

        items, total, _ = CitasRepository.list_paginated(
            page=1, page_size=20, fecha_desde=self.seguimiento, fecha_hasta=self.seguimiento,
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["motivo"], MOTIVO_SEGUIMIENTO)

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
