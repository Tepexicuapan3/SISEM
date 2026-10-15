"""F7: una nota cancelada (Visit.status == "cancelada") no admite hijos nuevos
(409 VISIT_CANCELLED) y se excluye de reportes (change cancelacion-nota-cascada)."""
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.consulta_medica.models import MedicalLeave, VisitConsultation
from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository
from apps.consulta_medica.tests.test_consultation_audit_api import (
    _ConsultationAuditApiTestBase,
    _noop_audit_hook,
)
from apps.consulta_medica.uses_case.consultation_usecase import (
    add_secondary_diagnosis,
    save_diagnosis,
    save_prescriptions,
)
from apps.consulta_medica.uses_case.medical_leave_usecase import create_medical_leave
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item
from apps.consulta_medica.uses_case.study_result_usecase import create_study_result
from apps.pases.models import Referral
from apps.pases.uses_case.referral_usecase import create_referral
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError


class VisitCancelledGuardTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        self.visit = self._visit_with_consultation()
        self.doctor_id = self.doctor_user.id_usuario
        Visit.objects.filter(pk=self.visit.pk).update(status="cancelada")

    def _assert_cancelled(self, call):
        with self.assertRaises(VisitDomainError) as ctx:
            call()
        self.assertEqual(ctx.exception.code, "VISIT_CANCELLED")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_create_medical_leave(self):
        self._assert_cancelled(lambda: create_medical_leave(
            self.visit.id_visit, ["DOCTOR"], leave_type_id=self.leave_type.pk, days=2,
            start_date=date.today(), is_subsequent=False, actor_id=self.doctor_id,
        ))
        self.assertEqual(MedicalLeave.objects.count(), 0)

    def test_create_referral(self):
        self._assert_cancelled(lambda: create_referral(
            self.visit.id_visit, ["DOCTOR"],
            referral_type=Referral.ReferralType.ESPECIALIDAD, actor_id=self.doctor_id,
        ))
        self.assertEqual(Referral.objects.count(), 0)

    def test_create_study_result(self):
        self._assert_cancelled(lambda: create_study_result(
            self.visit.id_visit, ["DOCTOR"], study_type_id=self.study_type.pk,
            result_date=date.today(), notes=None,
            file=SimpleUploadedFile("r.pdf", b"%PDF-1.4"), actor_id=self.doctor_id,
        ))

    def test_add_prescription_item(self):
        self._assert_cancelled(lambda: add_prescription_item(
            self.visit.id_visit, ["DOCTOR"], medication_id=self.med_basico.pk, quantity=1,
            indications="x", actor_id=self.doctor_id,
        ))

    def test_save_prescriptions(self):
        self._assert_cancelled(lambda: save_prescriptions(
            self.visit.id_visit, ["DOCTOR"], ["Reposo"], self.doctor_id,
            audit_hook=_noop_audit_hook,
        ))

    def test_add_secondary_diagnosis(self):
        self._assert_cancelled(lambda: add_secondary_diagnosis(
            self.visit.id_visit, ["DOCTOR"], cie_code="A090", doctor_id=self.doctor_id,
        ))

    def test_save_diagnosis(self):
        self._assert_cancelled(lambda: save_diagnosis(
            self.visit.id_visit, ["DOCTOR"], "Dx", "Nota", self.doctor_id,
            audit_hook=_noop_audit_hook,
        ))

    def test_visita_no_cancelada_sigue_funcionando(self):
        """Control: el guard no rompe el flujo normal (visita cerrada admite incapacidad)."""
        Visit.objects.filter(pk=self.visit.pk).update(status="cerrada")
        result = create_medical_leave(
            self.visit.id_visit, ["DOCTOR"], leave_type_id=self.leave_type.pk, days=2,
            start_date=date.today(), is_subsequent=False, actor_id=self.doctor_id,
        )
        self.assertEqual(result["status"], "emitida")
        leave = MedicalLeave.objects.get()
        self.assertEqual((leave.status, leave.rh_status), ("emitida", "no_enviada"))


class DailyReportExclusionTests(_ConsultationAuditApiTestBase):
    def test_consulta_de_visita_cancelada_no_cuenta_en_informe_diario(self):
        visit = self._visit_with_consultation()
        today = date.today()
        Visit.objects.filter(pk=visit.pk).update(status="cerrada", fecha_consulta=today)
        report = lambda: ConsultationRepository.list_daily_report(
            today - timedelta(days=1), today + timedelta(days=1),
        ).count()
        self.assertEqual(report(), 1)

        Visit.objects.filter(pk=visit.pk).update(status="cancelada")

        self.assertEqual(report(), 0)
        # La fila no se borro: sigue en la tabla.
        self.assertEqual(VisitConsultation.objects.filter(id_visit=visit).count(), 1)
