"""
Suite de auditoria de `consulta_medica` (Fase 6.3 del change
`auditoria-cirugias-ambulancias`, engram #514/#511/#512/#513).

Cubre las 16 acciones de auditoria de este dominio (D7 + excepcion A7 sobre
el camino critico de consulta -- `ConsultationStarted`/`DiagnosisSaved`/
`ConsultationClosed` son SIMPLE pese a mutar dominio dentro de `atomic()`):

- Clase 1 (ConsultationAuditEventTests): evento correcto, una por accion
  (recurso_tipo/recurso_id/datos_antes/datos_despues per tabla A3 de #511).
- Clase 2 (ConsultationAuditRollbackTests): rollback si falla el
  audit_hook, para los 8 ESTRICTOS vigentes.
- Clase 3 (ConsultationAuditSimpleTests): persiste aunque falle la
  auditoria, para los 8 SIMPLES vigentes (5 originales + 3 de A7).
- Clase 4 (ConsultationAuditPayloadTests): payload JSON-safe, invariante
  de 1-evento-por-request en ConsultationClosed (3 paths, los 3 toleran
  fallo de auditoria), guardas sin evento huerfano.
"""
import json
import tempfile
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCies, EstudiosMed, Licencias, Medicamentos, Permisos, Roles
from apps.consulta_medica.models import (
    ConsultationAddendum,
    MedicalLeave,
    OdontogramTooth,
    PrescriptionAuthorization,
    StomatologyHistory,
    StudyResult,
    VisitConsultation,
    VisitDiagnosis,
    VisitPrescription,
    VisitPrescriptionItem,
)
from apps.consulta_medica.repositories.clinical_history_repository import (
    ClinicalHistoryRepository,
)
from apps.consulta_medica.uses_case.consultation_usecase import (
    add_secondary_diagnosis,
    close_consultation,
    save_diagnosis,
)
from apps.consulta_medica.uses_case.prescription_item_usecase import add_prescription_item
from apps.recepcion.models import Visit

_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="sires_test_media_consulta_medica_audit_")

AUTHORIZE_PERMISSION = ["clinico:recetas:authorize"]


def _noop_audit_hook(**kwargs):
    """Setup-only: arma estado previo (consulta/consultation/diagnostico)
    sin generar el evento bajo prueba -- mismo criterio que
    `_noop_audit_hook` en los tests unitarios de usecase (A0.3)."""
    return None


class _ConsultationAuditApiTestBase(APITestCase):
    def setUp(self):
        self.request_id = "44444444-4444-4444-4444-444444444444"
        self.doctor_password = "Doctor_Audit_123456"
        self.authorizer_password = "Authorizer_Audit_123456"

        self.doctor_user = self._create_user_with_role(
            username="audit_doctor_user",
            email="audit.doctor@example.com",
            password=self.doctor_password,
            role_code="DOCTOR",
        )
        self.authorizer_user = self._create_user_with_role(
            username="audit_authorizer_user",
            email="audit.authorizer@example.com",
            password=self.authorizer_password,
            role_code="FARMACIA_AUDIT",
            permissions=["clinico:recetas:authorize"],
        )

        CatCies.objects.create(
            code="A090", description="GASTROENTERITIS", version="CIE-10", is_active=True,
        )

        self.leave_type = Licencias.objects.create(name="Enfermedad general")
        self.study_type = EstudiosMed.objects.create(
            name="Biometria Hematica", study_type="LAB",
            indication="Biometria hematica completa",
        )
        self.med_basico = Medicamentos.objects.create(
            name="Paracetamol 500mg", cuadro_basico=Medicamentos.CuadroBasico.BASICO,
            is_controlled=False,
        )
        self.med_especial = Medicamentos.objects.create(
            name="Medicamento Especial Audit", cuadro_basico=Medicamentos.CuadroBasico.ESPECIAL,
            is_controlled=False,
        )

        self._visit_seq = 0

    # ------------------------------------------------------------------
    # Helpers de usuarios / sesion
    # ------------------------------------------------------------------

    def _create_user_with_role(self, username, email, password, role_code, permissions=None):
        user = SyUsuario.objects.create(
            usuario=username, correo=email, clave_hash=make_password(password),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, paterno="Test", materno="User")
        role, _ = Roles.objects.get_or_create(
            rol=role_code, defaults={"desc_rol": f"Rol {role_code}", "landing_route": "/consultas"},
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        for permission_code in permissions or []:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code, defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        # Redis (sesion unica) no se limpia entre tests como la DB.
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": username, "password": password},
            format="json", HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def _login_doctor(self):
        self._login_as("audit_doctor_user", self.doctor_password)

    def _login_authorizer(self):
        self._login_as("audit_authorizer_user", self.authorizer_password)

    def _csrf_headers(self):
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    # ------------------------------------------------------------------
    # Helpers de dominio
    # ------------------------------------------------------------------

    def _make_visit(self, *, status_="lista_para_doctor"):
        self._visit_seq += 1
        n = self._visit_seq
        return Visit.objects.create(
            folio=f"AUD-{n}", no_exp=f"EXPAUD{n}",
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-AUD-{n}", status=status_,
        )

    def _visit_with_consultation(self, *, primary_diagnosis="Dx previo", final_note="Nota previa"):
        visit = self._make_visit(status_="en_consulta")
        save_diagnosis(
            visit.id_visit, ["DOCTOR"], primary_diagnosis, final_note,
            doctor_id=self.doctor_user.id_usuario, audit_hook=_noop_audit_hook,
        )
        return visit

    def _call_with_audit_down(self, request_callable):
        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            return request_callable()


# ======================================================================
# Clase 1 -- evento correcto, una por accion (16)
# ======================================================================


class ConsultationAuditEventTests(_ConsultationAuditApiTestBase):
    def test_consultation_started_writes_audit_event(self):
        visit = self._make_visit(status_="lista_para_doctor")
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/start", {}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(accion="ConsultationStarted", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.recurso_id, visit.id_visit)
        self.assertEqual(event.resultado, "SUCCESS")
        self.assertEqual(event.meta["module"], "consulta_medica")
        self.assertEqual(event.datos_antes, {"status": "lista_para_doctor"})
        self.assertEqual(
            event.datos_despues, {"status": "en_consulta", "doctorId": self.doctor_user.id_usuario},
        )

    def test_diagnosis_saved_writes_audit_event(self):
        visit = self._make_visit(status_="en_consulta")
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/diagnosis",
            {"primaryDiagnosis": "Gastroenteritis aguda", "finalNote": "Nota de evolucion"},
            format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(accion="DiagnosisSaved", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["visitId"], visit.id_visit)
        self.assertEqual(event.datos_despues["primaryDiagnosis"], "Gastroenteritis aguda")
        self.assertFalse(event.datos_despues["hasSubjective"])

    def test_clinical_history_updated_writes_audit_event(self):
        no_exp = "EXPAUDCH1"
        history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, 0)
        ClinicalHistoryRepository.update(
            history, fields={"phone": "5555555555"}, updated_by_id=self.doctor_user.id_usuario,
        )
        self._login_doctor()

        response = self.client.patch(
            f"/api/v1/patients/{no_exp}/clinical-history?pkNum=0",
            {"phone": "6666666666"}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(accion="ClinicalHistoryUpdated", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.datos_antes, {"phone": "5555555555"})
        self.assertEqual(event.datos_despues["phone"], "6666666666")
        self.assertEqual(event.datos_despues["changedFields"], ["phone"])
        self.assertTrue(event.datos_despues["revisionCreated"])

    def test_medical_leave_created_writes_audit_event(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/medical-leave",
            {
                "leaveTypeId": self.leave_type.id, "days": 3,
                "startDate": "2026-02-01", "isSubsequent": False,
            },
            format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = AuditoriaEvento.objects.get(accion="MedicalLeaveCreated", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.recurso_id, response.data["id"])
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["visitId"], visit.id_visit)
        self.assertEqual(event.datos_despues["leaveTypeId"], self.leave_type.id)
        self.assertEqual(event.datos_despues["days"], 3)
        self.assertEqual(event.datos_despues["startDate"], "2026-02-01")

    def test_odontogram_tooth_updated_writes_audit_event(self):
        no_exp = "EXPAUDOD1"
        self._login_doctor()

        response = self.client.patch(
            f"/api/v1/patients/{no_exp}/odontogram/11?pkNum=0",
            {"condition": "caries", "notes": "Caries superficial"}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(accion="OdontogramToothUpdated", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.datos_antes, {"condition": None, "notesLen": None})
        self.assertEqual(event.datos_despues["toothFdi"], "11")
        self.assertEqual(event.datos_despues["condition"], "caries")
        self.assertTrue(event.datos_despues["created"])

    def test_stomatology_history_updated_writes_audit_event(self):
        no_exp = "EXPAUDSTO1"
        self._login_doctor()

        response = self.client.patch(
            f"/api/v1/patients/{no_exp}/stomatology-history?pkNum=0",
            {"personalDiabetes": True, "habits": "Fuma ocasionalmente"}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(
            accion="StomatologyHistoryUpdated", request_id=self.request_id,
        )
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.datos_antes, {"personalDiabetes": False, "habitsLen": None})
        self.assertEqual(event.datos_despues["personalDiabetes"], True)
        self.assertEqual(event.datos_despues["habitsLen"], len("Fuma ocasionalmente"))
        self.assertEqual(event.datos_despues["changedFields"], ["habits", "personalDiabetes"])

    @override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
    def test_study_result_created_writes_audit_event(self):
        visit = self._visit_with_consultation()
        self._login_doctor()
        upload = SimpleUploadedFile(
            "resultado.pdf", b"%PDF-1.4 contenido", content_type="application/pdf",
        )

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/study-results",
            {
                "studyTypeId": self.study_type.id, "resultDate": "2026-02-01",
                "notes": "Resultado normal", "file": upload,
            },
            format="multipart", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = AuditoriaEvento.objects.get(accion="StudyResultCreated", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.recurso_id, response.data["id"])
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["visitId"], visit.id_visit)
        self.assertEqual(event.datos_despues["studyTypeId"], self.study_type.id)
        self.assertTrue(event.datos_despues["hasFile"])
        self.assertEqual(event.datos_despues["notesLen"], len("Resultado normal"))

    def test_secondary_diagnosis_added_writes_audit_event(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/diagnoses",
            {"cieCode": "A090", "notes": "Comorbilidad"}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = AuditoriaEvento.objects.get(accion="SecondaryDiagnosisAdded", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.recurso_id, response.data["id"])
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["visitId"], visit.id_visit)
        self.assertEqual(event.datos_despues["cieCode"], "A090")
        self.assertEqual(event.datos_despues["status"], "activo")

    def test_consultation_addendum_added_writes_audit_event(self):
        visit = self._visit_with_consultation()
        close_consultation(
            visit.id_visit, ["DOCTOR"], "Dx cierre", "Nota cierre",
            self.doctor_user.id_usuario, cie_code="A090", audit_hook=_noop_audit_hook,
        )
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/addenda",
            {"text": "Aclaracion posterior al cierre"}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = AuditoriaEvento.objects.get(
            accion="ConsultationAddendumAdded", request_id=self.request_id,
        )
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.recurso_id, response.data["id"])
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["textLen"], len("Aclaracion posterior al cierre"))

    def test_secondary_diagnosis_cancelled_writes_audit_event(self):
        visit = self._visit_with_consultation()
        diagnosis_payload = add_secondary_diagnosis(
            visit.id_visit, ["DOCTOR"], cie_code="A090", doctor_id=self.doctor_user.id_usuario,
        )
        self._login_doctor()

        response = self.client.patch(
            f"/api/v1/visits/{visit.id_visit}/diagnoses/{diagnosis_payload['id']}/cancel",
            {}, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(
            accion="SecondaryDiagnosisCancelled", request_id=self.request_id,
        )
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.datos_antes, {"status": "activo", "cieCode": "A090"})
        self.assertEqual(event.datos_despues, {"status": "cancelado", "cieCode": "A090"})

    def test_prescription_item_added_writes_audit_event(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/prescription-items",
            {
                "medicationId": self.med_basico.id, "quantity": 2,
                "indications": "Cada 8 horas", "dose": "500mg",
            },
            format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = AuditoriaEvento.objects.get(accion="PrescriptionItemAdded", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.recurso_id, response.data["id"])
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["visitId"], visit.id_visit)
        self.assertEqual(event.datos_despues["medicationId"], self.med_basico.id)
        self.assertFalse(event.datos_despues["requiresAuthorization"])

    def test_prescription_authorization_approved_writes_audit_event(self):
        visit = self._visit_with_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_especial.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_user.id_usuario,
        )
        auth = PrescriptionAuthorization.objects.get()
        self._login_authorizer()

        response = self.client.post(
            f"/api/v1/prescriptions/authorizations/{auth.id_authorization}/authorize",
            {}, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(
            accion="PrescriptionAuthorizationApproved", request_id=self.request_id,
        )
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.recurso_id, auth.id_authorization)
        self.assertEqual(
            event.datos_antes, {"status": "pendiente", "authorizedById": None, "authorizedAt": None},
        )
        self.assertEqual(event.datos_despues["status"], "autorizada")
        self.assertEqual(event.datos_despues["authorizedById"], self.authorizer_user.id_usuario)
        self.assertIsInstance(event.datos_despues["authorizedAt"], str)
        self.assertEqual(event.datos_despues["prescribedById"], self.doctor_user.id_usuario)
        self.assertEqual(event.datos_despues["specializedCount"], 1)

    def test_prescription_authorization_rejected_writes_audit_event(self):
        visit = self._visit_with_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_especial.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_user.id_usuario,
        )
        auth = PrescriptionAuthorization.objects.get()
        self._login_authorizer()

        response = self.client.post(
            f"/api/v1/prescriptions/authorizations/{auth.id_authorization}/reject",
            {"reason": "Sin existencias en farmacia"}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(
            accion="PrescriptionAuthorizationRejected", request_id=self.request_id,
        )
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(
            event.datos_antes,
            {"status": "pendiente", "authorizedById": None, "authorizedAt": None, "rejectionReason": None},
        )
        self.assertEqual(event.datos_despues["status"], "rechazada")
        self.assertEqual(event.datos_despues["rejectionReason"], "Sin existencias en farmacia")

    def test_prescription_item_cancelled_writes_audit_event(self):
        visit = self._visit_with_consultation()
        item_payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_basico.id, quantity=2,
            indications="Cada 8 horas", actor_id=self.doctor_user.id_usuario,
        )
        self._login_doctor()

        response = self.client.patch(
            f"/api/v1/visits/{visit.id_visit}/prescription-items/{item_payload['id']}/cancel",
            {}, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(
            accion="PrescriptionItemCancelled", request_id=self.request_id,
        )
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(
            event.datos_antes, {"status": "activo", "medicationId": self.med_basico.id, "quantity": 2},
        )
        self.assertEqual(
            event.datos_despues, {"status": "cancelado", "medicationId": self.med_basico.id, "quantity": 2},
        )

    def test_prescriptions_saved_writes_audit_event(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/prescriptions",
            {"items": ["Paracetamol 500mg cada 8h"]}, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(accion="PrescriptionsSaved", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["visitId"], visit.id_visit)
        self.assertEqual(event.datos_despues["itemsCount"], 1)
        self.assertEqual(event.datos_despues["items"], ["Paracetamol 500mg cada 8h"])

    def test_consultation_closed_writes_audit_event(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx cierre", "finalNote": "Nota final", "cieCode": "A090"},
            format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = AuditoriaEvento.objects.get(accion="ConsultationClosed", request_id=self.request_id)
        self.assertEqual(event.recurso_tipo, "consulta_medica")
        self.assertEqual(event.datos_antes["visitStatus"], "en_consulta")
        self.assertEqual(event.datos_despues["visitStatus"], "cerrada")
        self.assertFalse(event.datos_despues["isReplay"])


# ======================================================================
# Clase 2 -- rollback si falla el audit_hook (8 ESTRICTOS vigentes)
# ======================================================================


class ConsultationAuditRollbackTests(_ConsultationAuditApiTestBase):
    def _assert_rolls_back(self, request_callable, *, accion):
        response = self._call_with_audit_down(request_callable)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(AuditoriaEvento.objects.filter(accion=accion).count(), 0)
        return response

    def test_clinical_history_updated_rolls_back(self):
        no_exp = "EXPAUDCH2"
        history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, 0)
        ClinicalHistoryRepository.update(
            history, fields={"phone": "5555555555"}, updated_by_id=self.doctor_user.id_usuario,
        )
        self._login_doctor()

        self._assert_rolls_back(
            lambda: self.client.patch(
                f"/api/v1/patients/{no_exp}/clinical-history?pkNum=0",
                {"phone": "7777777777"}, format="json", **self._csrf_headers(),
            ),
            accion="ClinicalHistoryUpdated",
        )
        history.refresh_from_db()
        self.assertEqual(history.phone, "5555555555")

    def test_odontogram_tooth_updated_rolls_back(self):
        no_exp = "EXPAUDOD2"
        self._login_doctor()

        self._assert_rolls_back(
            lambda: self.client.patch(
                f"/api/v1/patients/{no_exp}/odontogram/11?pkNum=0",
                {"condition": "caries", "notes": "Nota"}, format="json", **self._csrf_headers(),
            ),
            accion="OdontogramToothUpdated",
        )
        self.assertFalse(
            OdontogramTooth.objects.filter(no_exp=no_exp, pk_num=0, tooth_fdi="11").exists(),
        )

    def test_stomatology_history_updated_rolls_back(self):
        no_exp = "EXPAUDSTO2"
        self._login_doctor()

        self._assert_rolls_back(
            lambda: self.client.patch(
                f"/api/v1/patients/{no_exp}/stomatology-history?pkNum=0",
                {"personalDiabetes": True}, format="json", **self._csrf_headers(),
            ),
            accion="StomatologyHistoryUpdated",
        )
        # get_or_create_for_patient corre ANTES del atomic() en el usecase
        # (fuera de la proteccion) -- la fila base existe, pero la edicion
        # (dentro del atomic) debe haberse revertido.
        history = StomatologyHistory.objects.get(no_exp=no_exp, pk_num=0)
        self.assertFalse(history.personal_diabetes)

    def test_secondary_diagnosis_cancelled_rolls_back(self):
        visit = self._visit_with_consultation()
        diagnosis_payload = add_secondary_diagnosis(
            visit.id_visit, ["DOCTOR"], cie_code="A090", doctor_id=self.doctor_user.id_usuario,
        )
        self._login_doctor()

        self._assert_rolls_back(
            lambda: self.client.patch(
                f"/api/v1/visits/{visit.id_visit}/diagnoses/{diagnosis_payload['id']}/cancel",
                {}, format="json", **self._csrf_headers(),
            ),
            accion="SecondaryDiagnosisCancelled",
        )
        diagnosis = VisitDiagnosis.objects.get(pk=diagnosis_payload["id"])
        self.assertEqual(diagnosis.status, "activo")

    def test_prescription_authorization_approved_rolls_back(self):
        visit = self._visit_with_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_especial.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_user.id_usuario,
        )
        auth = PrescriptionAuthorization.objects.get()
        self._login_authorizer()

        self._assert_rolls_back(
            lambda: self.client.post(
                f"/api/v1/prescriptions/authorizations/{auth.id_authorization}/authorize",
                {}, format="json", **self._csrf_headers(),
            ),
            accion="PrescriptionAuthorizationApproved",
        )
        auth.refresh_from_db()
        self.assertEqual(auth.status, PrescriptionAuthorization.Status.PENDIENTE)
        self.assertIsNone(auth.authorized_at)

    def test_prescription_authorization_rejected_rolls_back(self):
        visit = self._visit_with_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_especial.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_user.id_usuario,
        )
        auth = PrescriptionAuthorization.objects.get()
        self._login_authorizer()

        self._assert_rolls_back(
            lambda: self.client.post(
                f"/api/v1/prescriptions/authorizations/{auth.id_authorization}/reject",
                {"reason": "Sin existencias"}, format="json", **self._csrf_headers(),
            ),
            accion="PrescriptionAuthorizationRejected",
        )
        auth.refresh_from_db()
        self.assertEqual(auth.status, PrescriptionAuthorization.Status.PENDIENTE)
        self.assertIsNone(auth.rejection_reason)

    def test_prescription_item_cancelled_rolls_back(self):
        visit = self._visit_with_consultation()
        item_payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_basico.id, quantity=2,
            indications="Cada 8 horas", actor_id=self.doctor_user.id_usuario,
        )
        self._login_doctor()

        self._assert_rolls_back(
            lambda: self.client.patch(
                f"/api/v1/visits/{visit.id_visit}/prescription-items/{item_payload['id']}/cancel",
                {}, format="json", **self._csrf_headers(),
            ),
            accion="PrescriptionItemCancelled",
        )
        item = VisitPrescriptionItem.objects.get(pk=item_payload["id"])
        self.assertEqual(item.status, "activo")

    def test_prescriptions_saved_rolls_back(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        self._assert_rolls_back(
            lambda: self.client.post(
                f"/api/v1/visits/{visit.id_visit}/prescriptions",
                {"items": ["Paracetamol 500mg cada 8h"]}, format="json", **self._csrf_headers(),
            ),
            accion="PrescriptionsSaved",
        )
        self.assertFalse(VisitPrescription.objects.filter(id_visit=visit).exists())


# ======================================================================
# Clase 3 -- persiste aunque falle la auditoria (8 SIMPLES vigentes:
# 5 originales + 3 de A7)
# ======================================================================


class ConsultationAuditSimpleTests(_ConsultationAuditApiTestBase):
    def test_consultation_started_persists_even_if_audit_fails(self):
        visit = self._make_visit(status_="lista_para_doctor")
        self._login_doctor()

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/start", {}, format="json",
            **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visit.refresh_from_db()
        self.assertEqual(visit.status, "en_consulta")
        self.assertEqual(AuditoriaEvento.objects.filter(accion="ConsultationStarted").count(), 0)

    def test_diagnosis_saved_persists_even_if_audit_fails(self):
        visit = self._make_visit(status_="en_consulta")
        self._login_doctor()

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/diagnosis",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota"}, format="json",
            **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(VisitConsultation.objects.filter(id_visit=visit).exists())
        self.assertEqual(AuditoriaEvento.objects.filter(accion="DiagnosisSaved").count(), 0)

    def test_medical_leave_created_persists_even_if_audit_fails(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/medical-leave",
            {
                "leaveTypeId": self.leave_type.id, "days": 2,
                "startDate": "2026-02-01", "isSubsequent": False,
            },
            format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(MedicalLeave.objects.filter(folio=response.data["folio"]).exists())
        self.assertEqual(AuditoriaEvento.objects.filter(accion="MedicalLeaveCreated").count(), 0)

    @override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
    def test_study_result_created_persists_even_if_audit_fails(self):
        visit = self._visit_with_consultation()
        self._login_doctor()
        upload = SimpleUploadedFile(
            "resultado.pdf", b"%PDF-1.4 contenido", content_type="application/pdf",
        )

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/study-results",
            {"studyTypeId": self.study_type.id, "resultDate": "2026-02-01", "file": upload},
            format="multipart", **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(StudyResult.objects.filter(pk=response.data["id"]).exists())
        self.assertEqual(AuditoriaEvento.objects.filter(accion="StudyResultCreated").count(), 0)

    def test_secondary_diagnosis_added_persists_even_if_audit_fails(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/diagnoses",
            {"cieCode": "A090"}, format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(VisitDiagnosis.objects.filter(pk=response.data["id"]).exists())
        self.assertEqual(AuditoriaEvento.objects.filter(accion="SecondaryDiagnosisAdded").count(), 0)

    def test_consultation_addendum_added_persists_even_if_audit_fails(self):
        visit = self._visit_with_consultation()
        close_consultation(
            visit.id_visit, ["DOCTOR"], "Dx cierre", "Nota cierre",
            self.doctor_user.id_usuario, cie_code="A090", audit_hook=_noop_audit_hook,
        )
        self._login_doctor()

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/addenda",
            {"text": "Aclaracion"}, format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ConsultationAddendum.objects.filter(pk=response.data["id"]).exists())
        self.assertEqual(AuditoriaEvento.objects.filter(accion="ConsultationAddendumAdded").count(), 0)

    def test_prescription_item_added_persists_even_if_audit_fails(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/prescription-items",
            {"medicationId": self.med_basico.id, "quantity": 1, "indications": "Cada 8h"},
            format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(VisitPrescriptionItem.objects.filter(pk=response.data["id"]).exists())
        self.assertEqual(AuditoriaEvento.objects.filter(accion="PrescriptionItemAdded").count(), 0)

    def test_consultation_closed_persists_even_if_audit_fails(self):
        visit = self._visit_with_consultation()
        self._login_doctor()

        response = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx cierre", "finalNote": "Nota final", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visit.refresh_from_db()
        self.assertEqual(visit.status, "cerrada")
        self.assertEqual(AuditoriaEvento.objects.filter(accion="ConsultationClosed").count(), 0)


# ======================================================================
# Clase 4 -- payload JSON-safe, invariante ConsultationClosed, guardas
# ======================================================================


class ConsultationAuditPayloadTests(_ConsultationAuditApiTestBase):
    @override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
    def test_audit_payload_is_json_primitive_for_all_16_actions(self):
        self._login_doctor()

        visit = self._make_visit(status_="lista_para_doctor")
        self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/start", {}, format="json",
            **self._csrf_headers(),
        )
        self.client.post(
            f"/api/v1/visits/{visit.id_visit}/diagnosis",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota"}, format="json", **self._csrf_headers(),
        )
        self.client.post(
            f"/api/v1/visits/{visit.id_visit}/medical-leave",
            {
                "leaveTypeId": self.leave_type.id, "days": 2,
                "startDate": "2026-02-01", "isSubsequent": False,
            },
            format="json", **self._csrf_headers(),
        )
        upload = SimpleUploadedFile(
            "resultado.pdf", b"%PDF-1.4 contenido", content_type="application/pdf",
        )
        self.client.post(
            f"/api/v1/visits/{visit.id_visit}/study-results",
            {"studyTypeId": self.study_type.id, "resultDate": "2026-02-01", "file": upload},
            format="multipart", **self._csrf_headers(),
        )
        diag_response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/diagnoses",
            {"cieCode": "A090"}, format="json", **self._csrf_headers(),
        )
        self.client.patch(
            f"/api/v1/visits/{visit.id_visit}/diagnoses/{diag_response.data['id']}/cancel",
            {}, format="json", **self._csrf_headers(),
        )
        item_response = self.client.post(
            f"/api/v1/visits/{visit.id_visit}/prescription-items",
            {"medicationId": self.med_basico.id, "quantity": 1, "indications": "Cada 8h"},
            format="json", **self._csrf_headers(),
        )
        self.client.patch(
            f"/api/v1/visits/{visit.id_visit}/prescription-items/{item_response.data['id']}/cancel",
            {}, format="json", **self._csrf_headers(),
        )
        self.client.post(
            f"/api/v1/visits/{visit.id_visit}/prescriptions",
            {"items": ["Paracetamol 500mg"]}, format="json", **self._csrf_headers(),
        )
        self.client.patch(
            f"/api/v1/patients/{visit.no_exp}/clinical-history?pkNum=0",
            {"phone": "5555555555"}, format="json", **self._csrf_headers(),
        )
        self.client.patch(
            f"/api/v1/patients/{visit.no_exp}/odontogram/11?pkNum=0",
            {"condition": "caries"}, format="json", **self._csrf_headers(),
        )
        self.client.patch(
            f"/api/v1/patients/{visit.no_exp}/stomatology-history?pkNum=0",
            {"personalDiabetes": True}, format="json", **self._csrf_headers(),
        )
        add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_especial.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_user.id_usuario,
        )
        auth_reject = PrescriptionAuthorization.objects.get(prescription__id_visit=visit)

        visit2 = self._visit_with_consultation()
        add_prescription_item(
            visit2.id_visit, ["DOCTOR"], medication_id=self.med_especial.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_user.id_usuario,
        )
        auth_approve = PrescriptionAuthorization.objects.get(prescription__id_visit=visit2)

        self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx cierre", "finalNote": "Nota cierre", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        )
        self.client.post(
            f"/api/v1/visits/{visit.id_visit}/consultation/addenda",
            {"text": "Aclaracion final"}, format="json", **self._csrf_headers(),
        )

        self._login_authorizer()
        self.client.post(
            f"/api/v1/prescriptions/authorizations/{auth_reject.id_authorization}/reject",
            {"reason": "Sin existencias"}, format="json", **self._csrf_headers(),
        )
        self.client.post(
            f"/api/v1/prescriptions/authorizations/{auth_approve.id_authorization}/authorize",
            {}, format="json", **self._csrf_headers(),
        )

        events = AuditoriaEvento.objects.filter(recurso_tipo="consulta_medica")
        self.assertGreater(events.count(), 0)
        for event in events:
            # No debe lanzar TypeError -- todos los valores son primitivas
            # JSON-safe (D4): str/int/float/bool/None, sin date/datetime crudos.
            json.dumps(event.datos_antes)
            json.dumps(event.datos_despues)
            json.dumps(event.meta)

        accions = set(events.values_list("accion", flat=True))
        expected_accions = {
            "ConsultationStarted", "DiagnosisSaved", "MedicalLeaveCreated", "StudyResultCreated",
            "SecondaryDiagnosisAdded", "SecondaryDiagnosisCancelled", "PrescriptionItemAdded",
            "PrescriptionItemCancelled", "PrescriptionsSaved", "ClinicalHistoryUpdated",
            "OdontogramToothUpdated", "StomatologyHistoryUpdated", "ConsultationAddendumAdded",
            "ConsultationClosed", "PrescriptionAuthorizationApproved", "PrescriptionAuthorizationRejected",
        }
        self.assertEqual(accions, expected_accions)

    def test_close_consultation_logs_exactly_one_event_per_path(self):
        self._login_doctor()

        # Path principal: en_consulta -> cerrada.
        visit_main = self._visit_with_consultation()
        response_main = self.client.post(
            f"/api/v1/visits/{visit_main.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        )
        self.assertEqual(response_main.status_code, status.HTTP_200_OK)
        consultation_id = response_main.data["consultation"]["id"]
        self.assertEqual(
            AuditoriaEvento.objects.filter(
                accion="ConsultationClosed", recurso_id=consultation_id,
            ).count(),
            1,
        )

        # Path idempotente: mismo payload, visita ya cerrada.
        response_idempotent = self.client.post(
            f"/api/v1/visits/{visit_main.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        )
        self.assertEqual(response_idempotent.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AuditoriaEvento.objects.filter(
                accion="ConsultationClosed", recurso_id=consultation_id,
            ).count(),
            2,
        )

        # Path "cerrada sin consulta previa": visita cerrada por fuera del
        # flujo normal (sin VisitConsultation todavia).
        visit_no_consultation = self._make_visit(status_="cerrada")
        response_no_consultation = self.client.post(
            f"/api/v1/visits/{visit_no_consultation.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        )
        self.assertEqual(response_no_consultation.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AuditoriaEvento.objects.filter(
                accion="ConsultationClosed",
                recurso_id=response_no_consultation.data["consultation"]["id"],
            ).count(),
            1,
        )

    def test_close_consultation_all_paths_tolerate_audit_failure(self):
        self._login_doctor()

        visit_main = self._visit_with_consultation()
        response_main = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit_main.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response_main.status_code, status.HTTP_200_OK)

        response_idempotent = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit_main.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response_idempotent.status_code, status.HTTP_200_OK)

        visit_no_consultation = self._make_visit(status_="cerrada")
        response_no_consultation = self._call_with_audit_down(lambda: self.client.post(
            f"/api/v1/visits/{visit_no_consultation.id_visit}/consultation/close",
            {"primaryDiagnosis": "Dx", "finalNote": "Nota", "cieCode": "A090"},
            format="json", **self._csrf_headers(),
        ))
        self.assertEqual(response_no_consultation.status_code, status.HTTP_200_OK)

        self.assertEqual(AuditoriaEvento.objects.filter(accion="ConsultationClosed").count(), 0)

    def test_guards_write_no_event(self):
        self._login_doctor()

        visit = self._visit_with_consultation()

        # Guarda: diagnostico secundario inexistente.
        response_diag = self.client.patch(
            f"/api/v1/visits/{visit.id_visit}/diagnoses/999999/cancel",
            {}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(response_diag.status_code, status.HTTP_404_NOT_FOUND)

        # Guarda: item de receta inexistente.
        response_item = self.client.patch(
            f"/api/v1/visits/{visit.id_visit}/prescription-items/999999/cancel",
            {}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(response_item.status_code, status.HTTP_404_NOT_FOUND)

        # Guarda: autorizacion ya resuelta.
        add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.med_especial.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_user.id_usuario,
        )
        auth = PrescriptionAuthorization.objects.get()
        self._login_authorizer()
        first = self.client.post(
            f"/api/v1/prescriptions/authorizations/{auth.id_authorization}/authorize",
            {}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AuditoriaEvento.objects.filter(accion="PrescriptionAuthorizationApproved").count(), 1,
        )

        second = self.client.post(
            f"/api/v1/prescriptions/authorizations/{auth.id_authorization}/authorize",
            {}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            AuditoriaEvento.objects.filter(accion="PrescriptionAuthorizationApproved").count(), 1,
        )

        self.assertEqual(AuditoriaEvento.objects.filter(accion="SecondaryDiagnosisCancelled").count(), 0)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="PrescriptionItemCancelled").count(), 0)
