"""K1 de P-12: cancelar la nota tambien cancela su cita de seguimiento.

La cita se liga a la nota por la convencion de siempre: motivo
``MOTIVO_CITA_SEGUIMIENTO`` y notas "Consulta <folio de la visita>". Solo se
cancela si no tiene ficha (D4: si ya tiene, el paciente esta en la unidad y
la cita se deja). Ver docs/plans/p12-cita-seguimiento-analisis.md.
"""
import datetime

from django.utils import timezone

from apps.consulta_medica.models import ChangeLog, ConsultationCancellationItem
from apps.consulta_medica.tests.test_note_cancellation import _CancellationBase
from apps.consulta_medica.uses_case.note_cancellation_usecase import get_cancellation_preview
from apps.medicos.models import CatMedico
from apps.recepcion.models import (
    MOTIVO_CITA_SEGUIMIENTO,
    CanalMovimiento,
    CitaEstatusLog,
    CitaMedica,
    EstatusCita,
    Visit,
)

MOTIVO_NOTA_CANCELADA = "Consulta cancelada"


class NoteCancellationFollowUpTests(_CancellationBase):
    def setUp(self):
        super().setUp()
        self.medico = CatMedico.objects.create(id_usuario=self.doctor_user)

    def _cita(self, *, folio, notas=None, motivo=MOTIVO_CITA_SEGUIMIENTO,
              estatus=EstatusCita.AGENDADA):
        return CitaMedica.objects.create(
            folio=folio, patient=self.visit.patient, medico=self.medico, estatus=estatus,
            fecha_hora=timezone.now() + datetime.timedelta(days=10),
            servicio_tipo="medicina_general", motivo=motivo,
            notas=notas if notas is not None else f"Consulta {self.visit.folio}",
        )

    def test_cancela_la_cita_de_seguimiento_sin_ficha(self):
        cita = self._cita(folio="CIT-K1-1")

        result = self._cancel()

        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.CANCELADA)
        self.assertEqual(cita.motivo_cancelacion.name, MOTIVO_NOTA_CANCELADA)
        self.assertEqual(cita.cancelado_por_id, self.canceller.id_usuario)
        log = CitaEstatusLog.objects.filter(cita=cita).latest("pk")
        self.assertEqual(
            (log.from_status, log.to_status, log.canal),
            (EstatusCita.AGENDADA, EstatusCita.CANCELADA, CanalMovimiento.SISTEMA),
        )
        self.assertIn(f"#{result['cancellationId']}", log.notes)
        self.assertEqual(result["cascade"]["followUpAppointments"], 1)

    def test_la_cita_queda_en_la_traza_y_en_la_bitacora_de_cambios(self):
        cita = self._cita(folio="CIT-K1-2", estatus=EstatusCita.CONFIRMADA)

        result = self._cancel()

        item = ConsultationCancellationItem.objects.get(
            cancellation_id=result["cancellationId"],
            entity_type=ConsultationCancellationItem.EntityType.FOLLOW_UP_APPOINTMENT,
        )
        self.assertEqual(
            (item.entity_id, item.previous_status, item.new_status),
            (cita.pk, EstatusCita.CONFIRMADA, EstatusCita.CANCELADA),
        )
        self.assertTrue(
            ChangeLog.objects.filter(
                table=CitaMedica._meta.db_table,
                reason=ChangeLog.Reason.NOTE_CANCELLATION,
            ).exists()
        )

    def test_la_cita_con_ficha_se_deja(self):
        cita = self._cita(folio="CIT-K1-3")
        Visit.objects.create(
            folio="FICHA-K1-3", patient=self.visit.patient, arrival_type="appointment",
            appointment_id=cita.folio, status="en_espera",
        )

        result = self._cancel()

        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.AGENDADA)
        self.assertEqual(result["cascade"]["followUpAppointments"], 0)
        # D4: se deja, pero queda el aviso en la bitacora de la cita.
        log = CitaEstatusLog.objects.get(cita=cita)
        self.assertEqual(
            (log.from_status, log.to_status, log.canal, log.changed_by_id),
            (EstatusCita.AGENDADA, EstatusCita.AGENDADA, CanalMovimiento.SISTEMA,
             self.canceller.id_usuario),
        )
        self.assertIn(f"Nota cancelada #{result['cancellationId']}", log.notes)
        self.assertIn("ficha", log.notes)

    def test_no_toca_citas_de_otra_nota_ni_las_que_no_son_seguimiento_ni_las_terminadas(self):
        otra_nota = self._cita(folio="CIT-K1-4", notas="Consulta OTRO-FOLIO")
        otro_motivo = self._cita(folio="CIT-K1-5", motivo="Consulta general")
        atendida = self._cita(folio="CIT-K1-6", estatus=EstatusCita.ATENDIDA)

        result = self._cancel()

        for cita, estatus in (
            (otra_nota, EstatusCita.AGENDADA),
            (otro_motivo, EstatusCita.AGENDADA),
            (atendida, EstatusCita.ATENDIDA),
        ):
            cita.refresh_from_db()
            self.assertEqual(cita.estatus, estatus, cita.folio)
        self.assertEqual(result["cascade"]["followUpAppointments"], 0)

    def test_la_vista_previa_cuenta_la_cita_sin_cancelarla(self):
        cita = self._cita(folio="CIT-K1-7")

        preview = get_cancellation_preview(self.visit.id_visit, self.canceller, ["clinico:notas:cancel"])

        self.assertEqual(preview["cascade"]["followUpAppointments"], 1)
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.AGENDADA)

    def test_sin_cita_la_cancelacion_sigue_igual(self):
        result = self._cancel()

        self.assertEqual(result["visit"]["status"], "cancelada")
        self.assertEqual(result["cascade"]["followUpAppointments"], 0)
        self.assertFalse(
            ConsultationCancellationItem.objects.filter(
                entity_type=ConsultationCancellationItem.EntityType.FOLLOW_UP_APPOINTMENT,
            ).exists()
        )
