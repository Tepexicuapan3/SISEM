import datetime

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import CatCentroAtencion, CatTipoAlta, CatTipoHospitalizacion
from apps.hospitalizacion.models import HospitalAdmission, HospitalAdmissionRevision
from apps.hospitalizacion.repositories.hospital_admission_repository import HospitalAdmissionRepository
from apps.hospitalizacion.uses_case import hospital_admission_usecase
from apps.medicos.models import CatMedico


def _noop_audit_hook(**kwargs):
    return None


class HospitalAdmissionRevisionAppendOnlyTests(TestCase):
    """Requirement: Revisión append-only real (spec)."""

    def setUp(self):
        self.tipo_hosp = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        self.admission = HospitalAdmission.objects.create(
            no_exp="EXP0001",
            reason="Motivo inicial",
            admission_date=datetime.date(2026, 1, 1),
            admission_type=self.tipo_hosp,
        )

    def test_resaving_an_existing_revision_raises(self):
        revision = HospitalAdmissionRevision.objects.create(admission=self.admission, previous_reason="x")
        with self.assertRaises(ValidationError):
            revision.save()

    def test_deleting_an_existing_revision_raises(self):
        revision = HospitalAdmissionRevision.objects.create(admission=self.admission, previous_reason="x")
        with self.assertRaises(ValidationError):
            revision.delete()
        self.assertTrue(HospitalAdmissionRevision.objects.filter(pk=revision.pk).exists())

    def test_creating_a_new_revision_is_allowed(self):
        revision = HospitalAdmissionRevision.objects.create(admission=self.admission, previous_reason="x")
        self.assertIsNotNone(revision.pk)


class HospitalAdmissionRepositoryDirtyCheckTests(TestCase):
    """Requirement: Snapshot previo obligatorio / vacío no versiona (spec)."""

    def setUp(self):
        self.tipo_hosp = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        self.admission = HospitalAdmission.objects.create(
            no_exp="EXP0002",
            reason="Motivo inicial",
            admission_date=datetime.date(2026, 1, 1),
            admission_type=self.tipo_hosp,
            discharge_date=None,
        )

    def test_filling_empty_discharge_date_does_not_create_revision(self):
        HospitalAdmissionRepository.update(
            self.admission,
            fields={"discharge_date": datetime.date(2026, 1, 10)},
        )
        self.assertEqual(HospitalAdmissionRevision.objects.filter(admission=self.admission).count(), 0)

    def test_overwriting_existing_discharge_date_creates_revision_with_previous_value(self):
        HospitalAdmissionRepository.update(
            self.admission,
            fields={"discharge_date": datetime.date(2026, 1, 10)},
        )
        HospitalAdmissionRepository.update(
            self.admission,
            fields={"discharge_date": datetime.date(2026, 1, 15)},
            updated_by_id=7,
        )

        revisions = HospitalAdmissionRevision.objects.filter(admission=self.admission)
        self.assertEqual(revisions.count(), 1)
        revision = revisions.first()
        self.assertEqual(revision.previous_discharge_date, datetime.date(2026, 1, 10))
        self.assertEqual(revision.changed_by_id, 7)

        self.admission.refresh_from_db()
        self.assertEqual(self.admission.discharge_date, datetime.date(2026, 1, 15))

    def test_update_with_no_real_change_does_not_create_revision(self):
        HospitalAdmissionRepository.update(self.admission, fields={"reason": "Motivo inicial"})
        self.assertEqual(HospitalAdmissionRevision.objects.filter(admission=self.admission).count(), 0)

    def test_one_call_changing_multiple_fields_creates_exactly_one_revision(self):
        HospitalAdmissionRepository.update(
            self.admission,
            fields={"discharge_date": datetime.date(2026, 1, 10)},
        )
        HospitalAdmissionRepository.update(
            self.admission,
            fields={
                "reason": "Motivo corregido",
                "discharge_date": datetime.date(2026, 1, 20),
                "is_active": False,
            },
        )
        self.assertEqual(HospitalAdmissionRevision.objects.filter(admission=self.admission).count(), 1)

    def test_revision_snapshots_full_row_not_only_changed_fields(self):
        # is_scheduled nunca se toca en este update, pero la revision debe
        # traer su valor "previo" igual -- snapshot de fila completa.
        self.admission.is_scheduled = True
        self.admission.save()

        HospitalAdmissionRepository.update(
            self.admission,
            fields={"reason": "Otro motivo"},
        )
        revision = HospitalAdmissionRevision.objects.get(admission=self.admission)
        self.assertEqual(revision.previous_is_scheduled, True)
        self.assertEqual(revision.previous_reason, "Motivo inicial")


class ResolvePendingFkTests(TestCase):
    """Requirement: Resolución de FK sin revisión espuria (spec)."""

    def setUp(self):
        self.tipo_hosp = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        self.medico = CatMedico.objects.create(nombre_display="Dr. Prueba", legacy_cd_medico="0512")
        self.admission = HospitalAdmission.objects.create(
            no_exp="EXP0003",
            reason="Motivo",
            admission_date=datetime.date(2026, 1, 1),
            admission_type=self.tipo_hosp,
            admitting_doctor_code_legacy="0512",
        )

    def test_resolves_fk_without_creating_revision_or_touching_updated_at(self):
        original_updated_at = self.admission.updated_at

        resolved = hospital_admission_usecase.resolve_pending_fk(
            field="admitting_doctor",
            code_field="admitting_doctor_code_legacy",
            lookup={"0512": self.medico.id},
        )

        self.assertEqual(resolved, 1)
        self.admission.refresh_from_db()
        self.assertEqual(self.admission.admitting_doctor_id, self.medico.id)
        self.assertEqual(self.admission.updated_at, original_updated_at)
        self.assertEqual(HospitalAdmissionRevision.objects.filter(admission=self.admission).count(), 0)

    def test_writes_system_auditoria_evento(self):
        hospital_admission_usecase.resolve_pending_fk(
            field="admitting_doctor",
            code_field="admitting_doctor_code_legacy",
            lookup={"0512": self.medico.id},
        )
        evento = AuditoriaEvento.objects.get(accion="hsp_admission.resolve_pending_fk")
        self.assertEqual(evento.datos_despues["resolved"], 1)
        self.assertEqual(evento.actor_nombre, "Sistema")

    def test_guard_does_not_touch_already_resolved_fk(self):
        otro_medico = CatMedico.objects.create(nombre_display="Dr. Otro", legacy_cd_medico="9999")
        self.admission.admitting_doctor = self.medico
        self.admission.save()

        resolved = hospital_admission_usecase.resolve_pending_fk(
            field="admitting_doctor",
            code_field="admitting_doctor_code_legacy",
            lookup={"0512": otro_medico.id},
        )

        self.assertEqual(resolved, 0)
        self.admission.refresh_from_db()
        self.assertEqual(self.admission.admitting_doctor_id, self.medico.id)


class HospitalAdmissionUseCaseAtomicityTests(TestCase):
    """Requirement: transaction.atomic() cubre revisión + audit_hook."""

    def setUp(self):
        self.tipo_hosp = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        self.admission = HospitalAdmission.objects.create(
            no_exp="EXP0004",
            reason="Motivo inicial",
            admission_date=datetime.date(2026, 1, 1),
            admission_type=self.tipo_hosp,
            discharge_date=datetime.date(2026, 1, 10),
        )

    def test_audit_hook_failure_rolls_back_admission_and_revision(self):
        def failing_audit_hook(**kwargs):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            hospital_admission_usecase.update_admission(
                self.admission,
                fields={"discharge_date": datetime.date(2026, 1, 20)},
                audit_hook=failing_audit_hook,
            )

        self.admission.refresh_from_db()
        self.assertEqual(self.admission.discharge_date, datetime.date(2026, 1, 10))
        self.assertEqual(HospitalAdmissionRevision.objects.filter(admission=self.admission).count(), 0)

    def test_successful_update_creates_revision_and_calls_audit_hook(self):
        calls = []

        def audit_hook(**kwargs):
            calls.append(kwargs)

        hospital_admission_usecase.update_admission(
            self.admission,
            fields={"discharge_date": datetime.date(2026, 1, 20)},
            audit_hook=audit_hook,
        )

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["datos_despues"]["revisionCreated"])
        self.assertEqual(HospitalAdmissionRevision.objects.filter(admission=self.admission).count(), 1)


class HospitalAdmissionProtectTests(TestCase):
    """Requirement: on_delete=PROTECT en FK a catálogos/médicos."""

    def test_cannot_delete_referenced_discharge_type(self):
        tipo_hosp = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        tipo_alta = CatTipoAlta.objects.create(name="ALTA VOLUNTARIA", legacy_code=1)
        HospitalAdmission.objects.create(
            no_exp="EXP0005",
            reason="Motivo",
            admission_date=datetime.date(2026, 1, 1),
            admission_type=tipo_hosp,
            discharge_type=tipo_alta,
        )
        with self.assertRaises(ProtectedError):
            tipo_alta.delete()
