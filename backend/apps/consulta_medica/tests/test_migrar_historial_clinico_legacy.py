"""
Cobertura del comando `migrar_historial_clinico_legacy` -- no se puede probar
contra el MySQL legado real (sin acceso de red desde este entorno), asi que
se simula la conexion (`pymysql.connect`) para verificar la logica real:
resolucion de catalogos por NOMBRE, upsert por (no_exp, pk_num), preservacion
de `fe_hisclin` como `created_at`, y que --dry-run no escriba nada.
"""

import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from apps.catalogos.models import EdoCivil, Ocupaciones
from apps.consulta_medica.models import (
    ClinicalHistory,
    HistoricalNote,
    LegacyMigrationConflict,
    LegacyMigrationRun,
    Patient,
    PatientLegacySource,
)
from apps.consulta_medica.services.legacy_migration_control_service import apply_patient_fields

_LEGACY_ROW_BASE = {
    "no_hisclin": 1,
    "no_exp": "EXP-0001",
    "tp_paciente": 0,
    "fe_hisclin": None,
    "ds_telefono": "5555555555",
    "ds_antecedentes": "Sin antecedentes",
    "ds_padecimiento": "Dolor de cabeza",
    "ds_orgapasis": None,
    "ds_cabeza": None,
    "ds_cuello": None,
    "ds_torax": None,
    "ds_abdomen": None,
    "ds_genitales": None,
    "ds_miembros": None,
    "ds_mdiagnostico": None,
    "ds_mterapeutico": None,
    "ds_alergias": None,
    "ds_ocupacion": "Contador",
    "ds_escolaridad": None,
    "ds_edocivil": "Soltero",
    "ds_religion": None,
    "ds_residencia": None,
}


def _mock_conn(rows):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn


class MigrarHistorialClinicoLegacyTests(TestCase):
    def setUp(self):
        self.ocupacion = Ocupaciones.objects.create(name="Contador")
        self.edocivil = EdoCivil.objects.create(name="Soltero")

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_creates_clinical_history_resolving_catalogs_by_name(self, mock_connect):
        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE)])

        out = StringIO()
        call_command(
            "migrar_historial_clinico_legacy",
            host="x", user="x", password="x", database="x",
            stdout=out,
        )

        patient = Patient.objects.get(no_exp="EXP-0001", pk_num=0)
        history = ClinicalHistory.objects.get(no_exp="EXP-0001", pk_num=0)
        self.assertEqual(history.patient_id, patient.id_patient)
        self.assertEqual(patient.occupation_id, self.ocupacion.id)
        self.assertEqual(patient.marital_status_id, self.edocivil.id)
        self.assertIsNone(patient.religion_id)
        self.assertEqual(patient.phone, "5555555555")
        note = HistoricalNote.objects.get(no_exp="EXP-0001", section="padecimiento")
        self.assertEqual(note.content, "Dolor de cabeza")
        self.assertIn("Creados: 1", out.getvalue())

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_dry_run_does_not_write(self, mock_connect):
        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE)])

        out = StringIO()
        call_command(
            "migrar_historial_clinico_legacy",
            host="x", user="x", password="x", database="x",
            **{"dry_run": True},
            stdout=out,
        )

        self.assertFalse(ClinicalHistory.objects.filter(no_exp="EXP-0001").exists())
        self.assertIn("[dry-run]", out.getvalue())

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_upserts_on_second_run_instead_of_duplicating(self, mock_connect):
        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE)])
        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x", database="x")

        updated_row = dict(_LEGACY_ROW_BASE)
        updated_row["ds_padecimiento"] = "Actualizado"
        mock_connect.return_value = _mock_conn([updated_row])
        out = StringIO()
        call_command(
            "migrar_historial_clinico_legacy",
            host="x", user="x", password="x", database="x", stdout=out,
        )

        self.assertEqual(ClinicalHistory.objects.filter(no_exp="EXP-0001").count(), 1)
        # El texto historico se importa una sola vez por fila del legado
        # (idempotente por legacy_ref): no se duplica ni se pisa.
        notes = HistoricalNote.objects.filter(no_exp="EXP-0001", section="padecimiento")
        self.assertEqual(notes.count(), 1)
        self.assertIn("Actualizados: 1", out.getvalue())

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_reports_unmatched_catalog_value_and_leaves_null(self, mock_connect):
        row = dict(_LEGACY_ROW_BASE)
        row["ds_ocupacion"] = "Ocupacion Que No Existe En SISEM"
        mock_connect.return_value = _mock_conn([row])

        out = StringIO()
        call_command(
            "migrar_historial_clinico_legacy",
            host="x", user="x", password="x", database="x", stdout=out,
        )

        patient = Patient.objects.get(no_exp="EXP-0001", pk_num=0)
        self.assertIsNone(patient.occupation_id)
        self.assertIn("Ocupacion Que No Existe En SISEM", out.getvalue())

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_preserves_legacy_fecha_as_created_at(self, mock_connect):
        row = dict(_LEGACY_ROW_BASE)
        row["fe_hisclin"] = datetime.datetime(2019, 3, 15, 10, 0, 0)
        mock_connect.return_value = _mock_conn([row])

        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x", database="x")

        history = ClinicalHistory.objects.get(no_exp="EXP-0001", pk_num=0)
        self.assertEqual(str(history.created_at.date()), "2019-03-15")
        # HISTORIA_CLINICA.fe_apertura = fecha real del legado.
        self.assertEqual(str(history.opened_on), "2019-03-15")

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_skips_row_without_no_exp(self, mock_connect):
        row = dict(_LEGACY_ROW_BASE)
        row["no_exp"] = ""
        mock_connect.return_value = _mock_conn([row])

        out = StringIO()
        call_command(
            "migrar_historial_clinico_legacy",
            host="x", user="x", password="x", database="x", stdout=out,
        )

        self.assertEqual(ClinicalHistory.objects.count(), 0)
        self.assertIn("Errores: 1", out.getvalue())

    # ── Plan de migracion (seccion 8): bitacora y conflictos ────────────────

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_every_run_is_logged_with_operator_including_dry_run(self, mock_connect):
        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE)])
        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="secreto",
                     database="x", operador="ana.lopez", dry_run=True, stdout=StringIO())
        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE)])
        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="secreto",
                     database="x", operador="ana.lopez", stdout=StringIO())

        dry, real = LegacyMigrationRun.objects.order_by("id_run")
        self.assertTrue(dry.dry_run)
        self.assertFalse(real.dry_run)
        for run in (dry, real):
            self.assertEqual(run.command, "migrar_historial_clinico_legacy")
            self.assertEqual(run.operator, "ana.lopez")
            self.assertEqual(run.status, LegacyMigrationRun.Status.OK)
            self.assertEqual(run.rows_read, 1)
            self.assertIsNotNone(run.finished_at)
            self.assertNotIn("secreto", run.options)
        self.assertIn("Creados: 1", real.summary)

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_failed_run_is_logged_as_failed(self, mock_connect):
        mock_connect.side_effect = OSError("sin red")

        with self.assertRaises(Exception):
            call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x",
                         database="x", stdout=StringIO())

        run = LegacyMigrationRun.objects.get()
        self.assertEqual(run.status, LegacyMigrationRun.Status.FAILED)
        self.assertIsNotNone(run.summary)

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_rerun_never_overwrites_what_sires_edited(self, mock_connect):
        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE)])
        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x", database="x")
        Patient.objects.filter(no_exp="EXP-0001").update(phone="5511112222")

        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE, ds_ocupacion=None)])
        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x",
                     database="x", stdout=StringIO())

        patient = Patient.objects.get(no_exp="EXP-0001")
        self.assertEqual(patient.phone, "5511112222")
        # Legado vacio nunca borra lo que ya hay.
        self.assertEqual(patient.occupation_id, self.ocupacion.id)
        conflict = LegacyMigrationConflict.objects.get(field="phone")
        self.assertEqual(conflict.winner, LegacyMigrationConflict.Winner.SIRES)
        self.assertEqual((conflict.kept_value, conflict.discarded_value), ("5511112222", "5555555555"))
        self.assertEqual(conflict.run, LegacyMigrationRun.objects.latest("id_run"))


class PatientFieldConflictRuleTests(TestCase):
    """Regla de `apply_patient_fields`: gana el fe_hisclin mas reciente entre
    filas del legado (his_clinica / his_clinicad), sin importar el orden."""

    def setUp(self):
        self.patient = Patient.objects.create(no_exp="EXP-C", pk_num=0)
        self.contador = Ocupaciones.objects.create(name="Contador").id
        self.docente = Ocupaciones.objects.create(name="Docente").id
        self.chofer = Ocupaciones.objects.create(name="Chofer").id

    def _apply(self, occupation_id, ref, date):
        return apply_patient_fields(
            self.patient, {"occupation_id": occupation_id}, legacy_ref=ref, legacy_date=date,
        )

    def test_newer_legacy_row_wins_and_older_one_is_kept_out(self):
        self.assertEqual(self._apply(self.contador, "his_clinica:1", datetime.date(2019, 1, 1)), [])

        [newer] = self._apply(self.docente, "his_clinicad:7", datetime.date(2021, 5, 1))
        [older] = self._apply(self.chofer, "his_clinicad:3", datetime.date(2018, 1, 1))

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.occupation_id, self.docente)
        self.assertEqual(newer.winner, LegacyMigrationConflict.Winner.LEGACY_NEWER)
        self.assertEqual(older.winner, LegacyMigrationConflict.Winner.PREVIOUS_LEGACY)
        self.assertEqual(older.discarded_value, str(self.chofer))
        source = PatientLegacySource.objects.get(patient=self.patient, field="occupation_id")
        self.assertEqual((source.legacy_ref, source.legacy_date), ("his_clinicad:7", datetime.date(2021, 5, 1)))

    def test_value_edited_in_sires_is_kept_over_newer_legacy(self):
        self._apply(self.contador, "his_clinica:1", datetime.date(2019, 1, 1))
        self.patient.occupation_id = self.chofer
        self.patient.save(update_fields=["occupation_id"])

        [conflict] = self._apply(self.docente, "his_clinicad:9", datetime.date(2024, 1, 1))

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.occupation_id, self.chofer)
        self.assertEqual(conflict.winner, LegacyMigrationConflict.Winner.SIRES)

    def test_same_value_from_another_row_is_not_a_conflict(self):
        self._apply(self.contador, "his_clinica:1", datetime.date(2019, 1, 1))

        self.assertEqual(self._apply(self.contador, "his_clinicad:2", datetime.date(2020, 1, 1)), [])
        self.assertEqual(LegacyMigrationConflict.objects.count(), 0)
