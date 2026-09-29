from django.test import TestCase

from apps.consulta_medica.models import Allergy, AllergyRevision
from apps.consulta_medica.uses_case.allergy_usecase import (
    create_allergy,
    deactivate_allergy,
    list_allergies,
    update_allergy,
)
from apps.recepcion.services.errors import VisitDomainError


def _noop_audit_hook(**kwargs):
    """Unit-level: el audit_hook se valida en los tests de API. `audit_hook`
    es keyword-only requerido, asi que todo caller directo del usecase debe
    pasar algo."""
    return None


class AllergyUseCaseTests(TestCase):
    def setUp(self):
        self.no_exp = "EXP9101"
        self.pk_num = 0

    def test_create_allergy(self):
        payload = create_allergy(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"allergyTypeId": 5, "substance": "Nueces", "severity": "G", "reaction": "Anafilaxia"},
            actor_id=1,
            source="general",
            audit_hook=_noop_audit_hook,
        )

        self.assertEqual(payload["substance"], "Nueces")
        self.assertEqual(payload["source"], "general")
        self.assertTrue(payload["isActive"])
        self.assertEqual(AllergyRevision.objects.count(), 0)

    def test_update_allergy_creates_revision(self):
        created = create_allergy(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"allergyTypeId": 5, "substance": "Nueces", "severity": "G"},
            actor_id=1,
            source="general",
            audit_hook=_noop_audit_hook,
        )

        update_allergy(
            self.no_exp, self.pk_num, created["id"], ["DOCTOR"],
            {"severity": "M"},
            actor_id=2,
            audit_hook=_noop_audit_hook,
        )

        allergy = Allergy.objects.get(pk=created["id"])
        self.assertEqual(allergy.severity, "M")

        revisions = AllergyRevision.objects.filter(allergy=allergy)
        self.assertEqual(revisions.count(), 1)
        self.assertEqual(revisions.first().previous_severity, "G")
        self.assertEqual(revisions.first().changed_by_id, 2)

    def test_deactivate_allergy_excludes_it_from_list(self):
        created = create_allergy(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"allergyTypeId": 9, "substance": "Latex", "severity": "L"},
            actor_id=1,
            source="stomatology",
            audit_hook=_noop_audit_hook,
        )

        deactivate_allergy(
            self.no_exp, self.pk_num, created["id"], ["DOCTOR"], 1,
            audit_hook=_noop_audit_hook,
        )

        allergy = Allergy.objects.get(pk=created["id"])
        self.assertFalse(allergy.is_active)
        self.assertIsNotNone(allergy.deleted_at)

        result = list_allergies(self.no_exp, self.pk_num, ["DOCTOR"])
        self.assertEqual(result["items"], [])

    def test_list_allergies_visible_regardless_of_source(self):
        create_allergy(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"allergyTypeId": 1, "substance": "Penicilina", "severity": "G"},
            actor_id=1,
            source="general",
            audit_hook=_noop_audit_hook,
        )
        create_allergy(
            self.no_exp, self.pk_num, ["DOCTOR"],
            {"allergyTypeId": 2, "substance": "Lidocaina", "severity": "M"},
            actor_id=1,
            source="stomatology",
            audit_hook=_noop_audit_hook,
        )

        result = list_allergies(self.no_exp, self.pk_num, ["DOCTOR"])
        substances = {item["substance"] for item in result["items"]}
        self.assertEqual(substances, {"Penicilina", "Lidocaina"})

    def test_update_missing_allergy_raises(self):
        with self.assertRaises(VisitDomainError):
            update_allergy(
                self.no_exp, self.pk_num, 999999, ["DOCTOR"], {"severity": "L"},
                actor_id=1, audit_hook=_noop_audit_hook,
            )

    def test_list_allergies_without_doctor_role_raises(self):
        with self.assertRaises(VisitDomainError):
            list_allergies(self.no_exp, self.pk_num, roles=["RECEPCION"])
