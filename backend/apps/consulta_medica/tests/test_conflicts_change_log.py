"""
5.1 paso 11: los conflictos de migracion quedan en la bitacora unica
(motivo "CONFLICTO MIGRACION"), ademas de cns_conflicto_migracion.
"""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.consulta_medica.models import ChangeLog, LegacyMigrationConflict, Patient
from apps.consulta_medica.services.legacy_migration_control_service import (
    apply_patient_fields,
    backfill_conflicts_to_change_log,
)


def _conflicts():
    return ChangeLog.objects.filter(reason=ChangeLog.Reason.MIGRATION_CONFLICT)


class ConflictLoggedTests(TestCase):
    def test_un_conflicto_nuevo_queda_en_la_bitacora_con_el_valor_descartado(self):
        # El telefono lo capturo SIRES: el legado no lo pisa y se registra el conflicto.
        patient = Patient.objects.create(no_exp="100", pk_num=0, phone="5551111")

        apply_patient_fields(patient, {"phone": "5552222"}, legacy_ref="his_clinica:1", legacy_date=date(2020, 1, 1))

        self.assertEqual(LegacyMigrationConflict.objects.count(), 1)
        entrada = _conflicts().get()
        self.assertEqual(entrada.key, f"id_paciente|{patient.pk}")
        self.assertEqual(entrada.previous_value, {"phone": "5552222"})
        self.assertEqual(entrada.new_value, {"phone": "5551111"})
        self.assertEqual(entrada.user, "MIGRACION")

    def test_el_relleno_no_duplica_los_conflictos_que_ya_entraron(self):
        patient = Patient.objects.create(no_exp="100", pk_num=0, phone="5551111")
        apply_patient_fields(patient, {"phone": "5552222"}, legacy_ref="his_clinica:1", legacy_date=date(2020, 1, 1))

        counts = backfill_conflicts_to_change_log()

        self.assertEqual(counts, {"pasados": 0, "ya_estaban": 1, "sin_paciente": 0})
        self.assertEqual(_conflicts().count(), 1)


class BackfillTests(TestCase):
    def _old_conflict(self, no_exp="200", pk_num=0, field="occupation_id"):
        return LegacyMigrationConflict.objects.create(
            no_exp=no_exp, pk_num=pk_num, field=field, kept_value="3", discarded_value="7",
            legacy_ref="his_clinicad:9", legacy_date=date(2019, 5, 1),
            winner=LegacyMigrationConflict.Winner.PREVIOUS_LEGACY,
        )

    def test_pasa_los_conflictos_viejos_con_su_fecha_original(self):
        patient = Patient.objects.create(no_exp="200", pk_num=0)
        viejo = self._old_conflict()

        counts = backfill_conflicts_to_change_log()

        self.assertEqual(counts["pasados"], 1)
        entrada = _conflicts().get()
        self.assertEqual(entrada.key, f"id_paciente|{patient.pk}")
        self.assertEqual(entrada.occurred_at, viejo.created_at)
        self.assertEqual(entrada.previous_value, {"occupation_id": "7"})

    def test_es_idempotente(self):
        Patient.objects.create(no_exp="200", pk_num=0)
        self._old_conflict()
        backfill_conflicts_to_change_log()

        counts = backfill_conflicts_to_change_log()

        self.assertEqual(counts, {"pasados": 0, "ya_estaban": 1, "sin_paciente": 0})

    def test_dos_campos_del_mismo_paciente_entran_los_dos(self):
        Patient.objects.create(no_exp="200", pk_num=0)
        self._old_conflict(field="occupation_id")
        self._old_conflict(field="marital_status_id")

        self.assertEqual(backfill_conflicts_to_change_log()["pasados"], 2)

    def test_familiar_del_legado_encuentra_a_su_paciente_por_cd_familiar(self):
        Patient.objects.create(no_exp="200", pk_num=None, legacy_family_code=52895)
        self._old_conflict(pk_num=52895)

        self.assertEqual(backfill_conflicts_to_change_log()["pasados"], 1)

    def test_sin_paciente_se_cuenta_y_no_falla(self):
        self._old_conflict(no_exp="999")

        self.assertEqual(backfill_conflicts_to_change_log()["sin_paciente"], 1)

    def test_dry_run_no_escribe(self):
        Patient.objects.create(no_exp="200", pk_num=0)
        self._old_conflict()

        counts = backfill_conflicts_to_change_log(dry_run=True)

        self.assertEqual(counts["pasados"], 1)
        self.assertFalse(_conflicts().exists())

    def test_comando(self):
        Patient.objects.create(no_exp="200", pk_num=0)
        self._old_conflict()
        out = StringIO()

        call_command("pasar_conflictos_a_bitacora", stdout=out)

        self.assertIn("Pasados a la bitacora: 1", out.getvalue())
