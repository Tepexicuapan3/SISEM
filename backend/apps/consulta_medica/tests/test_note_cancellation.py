"""Cancelacion de nota en cascada (change cancelacion-nota-cascada, S18-S37).

Usecase + API sobre SQLite en memoria. La re-autenticacion usa el
`VerificadorSimple` REAL con un PolicyStore en memoria (sin Redis).
La concurrencia real (S33/S34) necesita Postgres: aqui se cubre la
serializacion logica (re-chequeo de estado/ya-cancelada y bloqueo por surtido).
"""
import hashlib
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.authentication.application.auth_policy_service import AuthPolicyService
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.firma import VerificadorSimple
from apps.authentication.tests.test_firma_verificador import FakePolicyStore
from apps.catalogos.models import MotivoCancelacionNota, Turnos
from apps.catalogos.models import Consultorios
from apps.catalogos.tests.designacion_factories import (
    make_center,
    make_designation,
)
from apps.consulta_medica.models import (
    ChangeLog,
    ConsultationCancellation,
    ConsultationCancellationItem,
    MedicalLeave,
    PrescriptionAuthorization,
    StudyResult,
    VisitConsultation,
    VisitDiagnosis,
    VisitPrescriptionItem,
)
from apps.consulta_medica.repositories.medical_leave_repository import MedicalLeaveRepository
from apps.consulta_medica.services.canonical_json import canonical_json, sha256_hex
from apps.consulta_medica.tests.test_consultation_audit_api import (
    _ConsultationAuditApiTestBase,
    _noop_audit_hook,
)
from apps.consulta_medica.uses_case.consultation_usecase import add_secondary_diagnosis
from apps.consulta_medica.uses_case.note_cancellation_usecase import (
    cancel_consultation,
    get_cancellation,
    get_cancellation_preview,
)
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item
from apps.pases.models import Referral, ReferralStudyDetail
from apps.pases.repositories.referral_repository import ReferralRepository
from apps.recepcion.models import Visit, VisitStatusLog
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import llave_publica

CANCEL_PERMS = ["clinico:notas:cancel"]
AUTH_PASSWORD = "Authorizer_Audit_123456"


def _real_verifier():
    return VerificadorSimple(policy_service=AuthPolicyService(FakePolicyStore()))


class _CancellationBase(_ConsultationAuditApiTestBase):
    """Nota CERRADA con toda la cascada: 1 dx secundario, receta con 2 items
    (uno ESPECIAL => autorizacion pendiente), pase con 2 estudios, incapacidad."""

    def setUp(self):
        super().setUp()
        self.center = make_center()
        turno = Turnos.objects.create(name="Matutino")
        self.consultorio = Consultorios.objects.create(
            name="C1", numero=1, id_turn=turno, id_center=self.center,
        )
        # Autorizador con permiso + designacion vigente que cubre el centro.
        self.canceller = self._create_user_with_role(
            username="note_canceller", email="canceller@example.com",
            password=AUTH_PASSWORD, role_code="AUTORIZADOR_NOTAS_TEST",
            permissions=CANCEL_PERMS,
        )
        self.designation = make_designation(
            self.canceller, scopes=[("CENTRO", self.center)],
        )
        self.motivo = MotivoCancelacionNota.objects.get(name="Error de captura")

        self.visit = self._visit_with_consultation(
            primary_diagnosis="Gastroenteritis", final_note="Nota final",
        )
        self.consultation = VisitConsultation.objects.get(id_visit=self.visit)
        add_secondary_diagnosis(
            self.visit.id_visit, ["DOCTOR"], cie_code="A090", notes="sec",
            doctor_id=self.doctor_user.id_usuario,
        )
        self.item_basico = add_prescription_item(
            self.visit.id_visit, ["DOCTOR"], medication_id=self.med_basico.id,
            quantity=2, indications="Cada 8h", actor_id=self.doctor_user.id_usuario,
        )
        self.item_especial = add_prescription_item(
            self.visit.id_visit, ["DOCTOR"], medication_id=self.med_especial.id,
            quantity=1, indications="Cada 12h", actor_id=self.doctor_user.id_usuario,
        )
        self.referral = ReferralRepository.create(
            consultation=self.consultation, no_exp=llave_publica(self.visit)[0], pk_num=0,
            referral_type=Referral.ReferralType.LABORATORIO, folio="REF-TEST-1",
        )
        for _ in range(2):
            ReferralRepository.add_study_detail(
                referral=self.referral, study_type=self.study_type,
            )
        self.leave = MedicalLeaveRepository.create(
            consultation=self.consultation, no_exp=llave_publica(self.visit)[0], pk_num=0,
            leave_type=self.leave_type, is_subsequent=False, days=3,
            start_date=date.today(), end_date=date.today() + timedelta(days=2),
            folio="LIC-20260101000000-EXP", created_by_id=self.doctor_user.id_usuario,
        )
        Visit.objects.filter(pk=self.visit.pk).update(
            status="cerrada", consultorio=self.consultorio,
        )
        self.visit.refresh_from_db()

    def _cancel(self, *, actor=None, perms=CANCEL_PERMS, password=AUTH_PASSWORD,
                motivo_id=None, detail=None, hook=None, verifier=None, visit_id=None):
        return cancel_consultation(
            visit_id or self.visit.id_visit, actor or self.canceller, perms,
            motivo_id=motivo_id if motivo_id is not None else self.motivo.pk,
            motivo_detalle=detail, password=password,
            audit_hook=hook or _noop_audit_hook,
            request_id="req-cancel-1", verifier=verifier or _real_verifier(),
        )

    def _snapshot_state(self):
        return {
            "visit": Visit.objects.get(pk=self.visit.pk).status,
            "dx": list(VisitDiagnosis.objects.order_by("pk").values_list("status", flat=True)),
            "rx": list(VisitPrescriptionItem.objects.order_by("pk").values_list("status", flat=True)),
            "auth": list(PrescriptionAuthorization.objects.order_by("pk").values_list("status", flat=True)),
            "ref": list(Referral.objects.order_by("pk").values_list("status", flat=True)),
            "study": list(ReferralStudyDetail.objects.order_by("pk").values_list("status", flat=True)),
            "leave": list(MedicalLeave.objects.order_by("pk").values_list("status", flat=True)),
            "cancellations": ConsultationCancellation.objects.count(),
        }

    def assertCode(self, exc_ctx, code, status_code):
        self.assertEqual(exc_ctx.exception.code, code)
        self.assertEqual(exc_ctx.exception.status_code, status_code)


class CancellationSuccessTests(_CancellationBase):
    def test_s30_cascada_completa_conserva_filas_y_cancela(self):
        before_counts = (
            VisitDiagnosis.objects.count(), VisitPrescriptionItem.objects.count(),
            PrescriptionAuthorization.objects.count(), Referral.objects.count(),
            ReferralStudyDetail.objects.count(), MedicalLeave.objects.count(),
        )
        self.assertEqual(
            PrescriptionAuthorization.objects.get().status, "pendiente",
        )

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            result = self._cancel(detail="se duplico")

        self.assertEqual(Visit.objects.get(pk=self.visit.pk).status, "cancelada")
        self.assertEqual(set(VisitDiagnosis.objects.values_list("status", flat=True)), {"cancelado"})
        self.assertEqual(set(VisitPrescriptionItem.objects.values_list("status", flat=True)), {"cancelado"})
        self.assertEqual(PrescriptionAuthorization.objects.get().status, "cancelada")
        self.assertEqual(Referral.objects.get().status, "cancelado")
        self.assertIsNone(Referral.objects.get().cancellation_reason_id)
        self.assertEqual(set(ReferralStudyDetail.objects.values_list("status", flat=True)), {"cancelado"})
        leave = MedicalLeave.objects.get()
        self.assertEqual((leave.status, leave.cancelled_by_id), ("cancelada", self.canceller.id_usuario))
        self.assertIsNotNone(leave.cancelled_at)
        # Ninguna fila se borro.
        self.assertEqual(before_counts, (
            VisitDiagnosis.objects.count(), VisitPrescriptionItem.objects.count(),
            PrescriptionAuthorization.objects.count(), Referral.objects.count(),
            ReferralStudyDetail.objects.count(), MedicalLeave.objects.count(),
        ))
        self.assertEqual(result["visit"], {"id": self.visit.id_visit, "status": "cancelada"})
        self.assertEqual(result["cascade"]["medicalLeaves"], 1)
        self.assertEqual(len(callbacks), 1)

    def test_s35_cabecera_items_hash_y_changelog(self):
        result = self._cancel(detail="x")

        header = ConsultationCancellation.objects.get()
        self.assertEqual(header.pk, result["cancellationId"])
        self.assertEqual(header.signature_method, "SIMPLE")
        self.assertEqual(len(header.content_hash), 64)
        self.assertEqual(header.authorizer_id, self.canceller.id_usuario)
        self.assertEqual(header.designation_id, self.designation.pk)
        self.assertEqual(header.applied_scope, "CENTRO")
        self.assertEqual(header.center_id, self.center.id)
        self.assertEqual(header.reason_id, self.motivo.pk)
        self.assertEqual(header.reason_detail, "x")
        self.assertEqual(header.consultation_id, self.consultation.pk)

        types = sorted(ConsultationCancellationItem.objects.values_list("entity_type", flat=True))
        self.assertEqual(types, sorted([
            "VISIT", "DIAGNOSIS", "RX_ITEM", "RX_ITEM", "RX_AUTH", "REFERRAL",
            "REFERRAL_STUDY", "REFERRAL_STUDY", "MEDICAL_LEAVE",
        ]))
        visit_item = ConsultationCancellationItem.objects.get(entity_type="VISIT")
        self.assertEqual((visit_item.previous_status, visit_item.new_status), ("cerrada", "cancelada"))

        self.assertEqual(
            ChangeLog.objects.filter(reason=ChangeLog.Reason.NOTE_CANCELLATION).count(), 9,
        )
        log = VisitStatusLog.objects.filter(visit=self.visit, to_status="cancelada").get()
        self.assertEqual(log.from_status, "cerrada")
        self.assertEqual(log.notes, f"NOTA CANCELADA #{header.pk}")

    def test_s36_hash_recalculado_coincide_con_snapshot_guardado(self):
        self._cancel()
        header = ConsultationCancellation.objects.get()
        stored = ConsultationCancellation.objects.filter(pk=header.pk).values_list(
            "canonical_snapshot", flat=True,
        ).first()
        self.assertEqual(hashlib.sha256(stored.encode("utf-8")).hexdigest(), header.content_hash)
        # El snapshot es el estado ANTERIOR (items aun activos, visita cerrada).
        self.assertIn('"status":"cerrada"', stored)
        self.assertIn('"schema":"cancelacion-nota/v1"', stored)
        self.assertEqual(sha256_hex(canonical_json(__import__("json").loads(stored))), header.content_hash)

    def test_s31_autorizacion_ya_resuelta_no_se_altera(self):
        PrescriptionAuthorization.objects.update(status="rechazada", rejection_reason="no")

        self._cancel()

        self.assertEqual(PrescriptionAuthorization.objects.get().status, "rechazada")
        self.assertFalse(
            ConsultationCancellationItem.objects.filter(entity_type="RX_AUTH").exists()
        )

    def test_s23_fuera_de_adscripcion_marcado(self):
        other = make_center()
        self.canceller.detalle.id_centro_atencion = other
        self.canceller.detalle.save()
        self.assertTrue(self._cancel()["fueraAdscripcion"])
        self.assertTrue(ConsultationCancellation.objects.get().outside_assignment)

    def test_s23_dentro_de_adscripcion_no_marcado(self):
        self.canceller.detalle.id_centro_atencion = self.center
        self.canceller.detalle.save()
        self.assertFalse(self._cancel()["fueraAdscripcion"])

    def test_s37_evento_realtime_solo_tras_commit(self):
        with patch(
            "apps.consulta_medica.uses_case.note_cancellation_usecase.publish_visit_cancelled"
        ) as publish:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                result = self._cancel()
            publish.assert_not_called()  # aun no hubo commit
            callbacks[0]()
        publish.assert_called_once()
        kwargs = publish.call_args.kwargs
        self.assertEqual(kwargs["previous_status"], "cerrada")
        self.assertEqual(kwargs["status"], "cancelada")
        self.assertEqual(kwargs["note_cancellation_id"], result["cancellationId"])

    def test_incapacidad_cancelada_libera_traslape_y_sale_de_reportes(self):
        self.assertIsNotNone(
            MedicalLeaveRepository.get_active_overlap_for_patient(
                llave_publica(self.visit)[0], 0, date.today(),
            )
        )
        self._cancel()
        self.assertIsNone(
            MedicalLeaveRepository.get_active_overlap_for_patient(
                llave_publica(self.visit)[0], 0, date.today(),
            )
        )
        self.assertIsNone(MedicalLeaveRepository.get_active_for_consultation(self.consultation))
        self.assertEqual(
            MedicalLeaveRepository.list_report(
                date.today() - timedelta(days=1), date.today() + timedelta(days=5),
            ).count(),
            0,
        )


class CancellationAuthorizationTests(_CancellationBase):
    def _assert_untouched(self, before):
        self.assertEqual(self._snapshot_state(), before)
        self.assertEqual(ConsultationCancellation.objects.count(), 0)

    def test_s18_sin_permiso_403(self):
        before = self._snapshot_state()
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel(perms=[])
        self.assertCode(ctx, "ROLE_NOT_ALLOWED", 403)
        self._assert_untouched(before)

    def test_s19_sin_designacion_que_cubra_el_centro(self):
        other_center = make_center()
        DesignacionOtro = make_designation(scopes=[("CENTRO", other_center)])
        before = self._snapshot_state()
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel(actor=DesignacionOtro.user)
        self.assertCode(ctx, "AUTHORIZER_NOT_DESIGNATED", 403)
        self._assert_untouched(before)

    def test_s20_contrasena_incorrecta_403_reauth_failed(self):
        before = self._snapshot_state()
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel(password="Incorrecta_1")
        self.assertCode(ctx, "REAUTH_FAILED", 403)
        self._assert_untouched(before)

    def test_s21_lock_tras_intentos_fallidos_423_aun_con_clave_correcta(self):
        verifier = _real_verifier()
        for _ in range(5):
            with self.assertRaises(VisitDomainError):
                self._cancel(password="Mala_1", verifier=verifier)
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel(password=AUTH_PASSWORD, verifier=verifier)
        self.assertCode(ctx, "REAUTH_LOCKED", 423)
        self.assertEqual(ConsultationCancellation.objects.count(), 0)

    def test_s22_sin_motivo_422(self):
        with self.assertRaises(VisitDomainError) as ctx:
            cancel_consultation(
                self.visit.id_visit, self.canceller, CANCEL_PERMS, motivo_id=None,
                password=AUTH_PASSWORD, audit_hook=_noop_audit_hook, verifier=_real_verifier(),
            )
        self.assertCode(ctx, "VALIDATION_ERROR", 422)

    def test_motivo_inexistente_422(self):
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel(motivo_id=999999)
        self.assertCode(ctx, "VALIDATION_ERROR", 422)

    def test_autocancelacion_prohibida_403(self):
        # El autorizador es el medico tratante de la nota.
        VisitConsultation.objects.filter(pk=self.consultation.pk).update(doctor=self.canceller)
        before = self._snapshot_state()
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel()
        self.assertCode(ctx, "SELF_AUTHORIZATION_NOT_ALLOWED", 403)
        self._assert_untouched(before)

    def test_centro_no_resoluble_422(self):
        Visit.objects.filter(pk=self.visit.pk).update(consultorio=None)
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel()
        self.assertCode(ctx, "NOTE_CENTER_UNRESOLVED", 422)

    def test_error_de_servicio_del_verificador_se_convierte_en_domain_error(self):
        class Down:
            def verificar(self, *a, **k):
                raise AuthServiceError("SERVICE_UNAVAILABLE", "caido", 503)

        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel(verifier=Down())
        self.assertCode(ctx, "SERVICE_UNAVAILABLE", 503)


class CancellationBlockersTests(_CancellationBase):
    def _assert_blocked(self, code):
        before = self._snapshot_state()
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel()
        self.assertCode(ctx, code, 409)
        self.assertEqual(self._snapshot_state(), before)
        self.assertEqual(ChangeLog.objects.filter(reason=ChangeLog.Reason.NOTE_CANCELLATION).count(), 0)
        return ctx.exception

    def test_s24_visita_no_cerrada(self):
        Visit.objects.filter(pk=self.visit.pk).update(status="en_consulta")
        self._assert_blocked("VISIT_STATE_INVALID")

    def test_s25_ya_cancelada_no_genera_segundo_registro(self):
        self._cancel()
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel()
        self.assertCode(ctx, "NOTE_ALREADY_CANCELLED", 409)
        self.assertEqual(ConsultationCancellation.objects.count(), 1)

    def test_s34_cabecera_existente_con_visita_cerrada_no_duplica(self):
        # Simula la carrera: otra transaccion ya inserto la cabecera.
        self._cancel()
        Visit.objects.filter(pk=self.visit.pk).update(status="cerrada")
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel()
        self.assertCode(ctx, "NOTE_ALREADY_CANCELLED", 409)
        self.assertEqual(ConsultationCancellation.objects.count(), 1)

    def test_s26_item_surtido_parcialmente(self):
        VisitPrescriptionItem.objects.filter(pk=self.item_basico["id"]).update(
            dispensed_quantity=1, dispensation_status="parcial",
        )
        exc = self._assert_blocked("PRESCRIPTION_ITEM_DISPENSED")
        self.assertEqual(exc.details["blockers"][0]["ids"], [self.item_basico["id"]])

    def test_s27_incapacidad_enviada_a_rh(self):
        MedicalLeave.objects.update(rh_status="enviada")
        self._assert_blocked("LEAVE_SENT_TO_RH")

    def test_s27_incapacidad_verificada_por_rh(self):
        MedicalLeave.objects.update(rh_status="verificada")
        self._assert_blocked("LEAVE_SENT_TO_RH")

    def test_s29_folio_presente_en_replica_rh_bloquea(self):
        with patch(
            "apps.consulta_medica.uses_case.note_cancellation_usecase.find_folios_in_rh",
            return_value={self.leave.folio},
        ):
            self._assert_blocked("LEAVE_SENT_TO_RH")

    def test_s29_folio_ausente_en_replica_rh_es_cancelable(self):
        with patch(
            "apps.consulta_medica.uses_case.note_cancellation_usecase.find_folios_in_rh",
            return_value=set(),
        ):
            self._cancel()
        self.assertEqual(MedicalLeave.objects.get().status, "cancelada")

    def test_s28_resultado_de_estudio_activo_de_la_consulta(self):
        StudyResult.objects.create(
            consultation=self.consultation, no_exp=llave_publica(self.visit)[0], pk_num=0,
            study_type=self.study_type, result_date=date.today(), file="x.pdf",
        )
        self._assert_blocked("STUDY_RESULT_ACTIVE")

    def test_s28_resultado_ligado_a_estudio_de_pase(self):
        detail = ReferralStudyDetail.objects.first()
        StudyResult.objects.create(
            consultation=self.consultation, no_exp=llave_publica(self.visit)[0], pk_num=0,
            study_type=self.study_type, result_date=date.today(), file="x.pdf",
            referral_study=detail,
        )
        self._assert_blocked("STUDY_RESULT_ACTIVE")

    def test_resultado_inactivo_no_bloquea(self):
        StudyResult.objects.create(
            consultation=self.consultation, no_exp=llave_publica(self.visit)[0], pk_num=0,
            study_type=self.study_type, result_date=date.today(), file="x.pdf",
            is_active=False,
        )
        self._cancel()

    def test_varios_bloqueos_se_listan_todos(self):
        VisitPrescriptionItem.objects.filter(pk=self.item_basico["id"]).update(
            dispensed_quantity=1, dispensation_status="parcial",
        )
        MedicalLeave.objects.update(rh_status="enviada")
        exc = self._assert_blocked("PRESCRIPTION_ITEM_DISPENSED")
        self.assertEqual(
            [b["code"] for b in exc.details["blockers"]],
            ["PRESCRIPTION_ITEM_DISPENSED", "LEAVE_SENT_TO_RH"],
        )

    def test_s33_surtido_posterior_a_cancelacion_no_encuentra_items_activos(self):
        """Quien gana primero: tras cancelar, la dispensa (filtra status=activo) ya no los ve."""
        from apps.consulta_medica.repositories.prescription_dispensation_repository import (
            PrescriptionDispensationRepository,
        )

        self._cancel()
        locked = PrescriptionDispensationRepository.lock_items_for_dispense(
            [self.item_basico["id"], self.item_especial["id"]]
        )
        self.assertEqual(locked, [])


class CancellationAtomicityTests(_CancellationBase):
    def test_s32_fallo_en_incapacidades_deja_todo_sin_cambios(self):
        before = self._snapshot_state()
        with patch(
            "apps.consulta_medica.uses_case.note_cancellation_usecase."
            "MedicalLeaveRepository.cancel",
            side_effect=RuntimeError("boom"),
        ):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                with self.assertRaises(RuntimeError):
                    self._cancel()
        self.assertEqual(self._snapshot_state(), before)
        self.assertEqual(ConsultationCancellationItem.objects.count(), 0)
        self.assertEqual(ChangeLog.objects.filter(reason=ChangeLog.Reason.NOTE_CANCELLATION).count(), 0)
        self.assertEqual(VisitStatusLog.objects.filter(visit=self.visit, to_status="cancelada").count(), 0)
        self.assertEqual(callbacks, [])

    def test_fallo_del_audit_hook_estricto_hace_rollback_total(self):
        def failing_hook(**kwargs):
            raise RuntimeError("audit down")

        before = self._snapshot_state()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            with self.assertRaises(RuntimeError):
                self._cancel(hook=failing_hook)
        self.assertEqual(self._snapshot_state(), before)
        self.assertEqual(ConsultationCancellationItem.objects.count(), 0)
        self.assertEqual(callbacks, [])

    def test_el_audit_hook_recibe_meta_de_auditoria(self):
        captured = {}

        def hook(**kwargs):
            captured.update(kwargs)

        self._cancel(hook=hook)
        self.assertTrue(captured["strict"])
        self.assertEqual(captured["meta"]["alcance"], "CENTRO")
        self.assertEqual(len(captured["meta"]["hash"]), 64)
        self.assertIn("fueraAdscripcion", captured["meta"])


class CancellationPreviewTests(_CancellationBase):
    def test_preview_cancelable_con_conteos(self):
        data = get_cancellation_preview(self.visit.id_visit, self.canceller, CANCEL_PERMS)
        self.assertTrue(data["cancelable"])
        self.assertEqual(data["blockers"], [])
        self.assertTrue(data["puedeAutorizar"])
        self.assertEqual(data["cascade"]["prescriptionItems"], 2)
        self.assertEqual(data["cascade"]["referralStudies"], 2)
        self.assertEqual(data["centroId"], self.center.id)

    def test_preview_no_modifica_nada(self):
        before = self._snapshot_state()
        get_cancellation_preview(self.visit.id_visit, self.canceller, CANCEL_PERMS)
        self.assertEqual(self._snapshot_state(), before)

    def test_preview_con_bloqueo_no_es_cancelable(self):
        MedicalLeave.objects.update(rh_status="enviada")
        data = get_cancellation_preview(self.visit.id_visit, self.canceller, CANCEL_PERMS)
        self.assertFalse(data["cancelable"])
        self.assertEqual(data["blockers"][0]["code"], "LEAVE_SENT_TO_RH")

    def test_preview_sin_designacion(self):
        stranger = make_designation(scopes=[("CENTRO", make_center())]).user
        data = get_cancellation_preview(self.visit.id_visit, stranger, CANCEL_PERMS)
        self.assertFalse(data["puedeAutorizar"])
        self.assertFalse(data["cancelable"])

    def test_preview_sin_permiso_403(self):
        with self.assertRaises(VisitDomainError) as ctx:
            get_cancellation_preview(self.visit.id_visit, self.canceller, [])
        self.assertCode(ctx, "ROLE_NOT_ALLOWED", 403)

    def test_get_cancellation_404_si_no_existe_y_200_tras_cancelar(self):
        with self.assertRaises(VisitDomainError) as ctx:
            get_cancellation(self.visit.id_visit, CANCEL_PERMS)
        self.assertCode(ctx, "CANCELLATION_NOT_FOUND", 404)
        self._cancel()
        data = get_cancellation(self.visit.id_visit, CANCEL_PERMS)
        self.assertEqual(data["metodoFirma"], "SIMPLE")
        self.assertEqual(len(data["items"]), 9)


class CancellationApiTests(_CancellationBase):
    def _login_canceller(self):
        self._login_as("note_canceller", AUTH_PASSWORD)

    def _post(self, body, visit_id=None):
        return self.client.post(
            f"/api/v1/visits/{visit_id or self.visit.id_visit}/consultation/cancel",
            body, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def _patched_verifier(self):
        return patch(
            "apps.consulta_medica.uses_case.note_cancellation_usecase.VerificadorSimple",
            side_effect=lambda: _real_verifier(),
        )

    def test_post_cancel_200_y_auditoria(self):
        self._login_canceller()
        with self._patched_verifier():
            response = self._post({
                "motivoId": self.motivo.pk, "motivoDetalle": "dup", "password": AUTH_PASSWORD,
            })
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["visit"]["status"], "cancelada")
        self.assertEqual(response.data["metodoFirma"], "SIMPLE")
        event = AuditoriaEvento.objects.get(
            accion="ConsultationNoteCancelled", request_id=self.request_id,
        )
        self.assertEqual(event.resultado, "SUCCESS")
        self.assertEqual(event.recurso_id, response.data["cancellationId"])
        self.assertEqual(event.meta["alcance"], "CENTRO")
        self.assertEqual(event.meta["hash"], response.data["hashContenido"])
        self.assertNotIn(AUTH_PASSWORD, str(event.meta) + str(event.datos_antes) + str(event.datos_despues))

    def test_post_contrasena_incorrecta_es_403_nunca_401(self):
        self._login_canceller()
        with self._patched_verifier():
            response = self._post({"motivoId": self.motivo.pk, "password": "Mala_123"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "REAUTH_FAILED")

    def test_r26_reauth_fallida_registra_log_event_sin_password_ni_rollback(self):
        self._login_canceller()
        before = self._snapshot_state()
        with self._patched_verifier():
            response = self._post({"motivoId": self.motivo.pk, "password": "Mala_123"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        event = AuditoriaEvento.objects.get(
            accion="ConsultationNoteCancelReauthFailed", request_id=self.request_id,
        )
        self.assertEqual(event.resultado, "FAILURE")
        self.assertEqual(event.codigo_error, "REAUTH_FAILED")
        self.assertNotIn("Mala_123", str(event.meta) + str(event.datos_antes) + str(event.datos_despues))
        self.assertEqual(self._snapshot_state(), before)
        self.assertEqual(ConsultationCancellation.objects.count(), 0)

    def test_post_sin_password_422(self):
        self._login_canceller()
        response = self._post({"motivoId": self.motivo.pk})
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_post_sin_permiso_403(self):
        self._login_doctor()
        response = self._post({"motivoId": self.motivo.pk, "password": "x"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ROLE_NOT_ALLOWED")

    def test_post_audit_caido_hace_rollback_y_no_deja_nada(self):
        self._login_canceller()
        before = self._snapshot_state()
        with self._patched_verifier():
            try:
                self._call_with_audit_down(lambda: self._post(
                    {"motivoId": self.motivo.pk, "password": AUTH_PASSWORD}
                ))
            except Exception:
                pass
        self.assertEqual(self._snapshot_state(), before)

    def test_get_preview_y_get_cancellation(self):
        self._login_canceller()
        preview = self.client.get(
            f"/api/v1/visits/{self.visit.id_visit}/consultation/cancellation-preview"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertTrue(preview.data["cancelable"])
        missing = self.client.get(
            f"/api/v1/visits/{self.visit.id_visit}/consultation/cancellation"
        )
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        with self._patched_verifier():
            self._post({"motivoId": self.motivo.pk, "password": AUTH_PASSWORD})
        found = self.client.get(
            f"/api/v1/visits/{self.visit.id_visit}/consultation/cancellation"
        )
        self.assertEqual(found.status_code, status.HTTP_200_OK)
        self.assertEqual(found.data["motivoNombre"], "Error de captura")

    def test_get_preview_sin_sesion_401(self):
        self.client.cookies.clear()
        response = self.client.get(
            f"/api/v1/visits/{self.visit.id_visit}/consultation/cancellation-preview"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
