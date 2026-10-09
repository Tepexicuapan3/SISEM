"""
5.2 paso 5: trazabilidad del legado. ALERGIA.texto_original y
HISTORIA_CLINICA.tabla_origen / no_hisclin_origen, tanto al importar como en
el relleno de lo ya migrado (migracion 0049, solo con evidencia).
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from apps.catalogos.models import EdoCivil, Ocupaciones
from apps.consulta_medica.models import Allergy, ClinicalHistory
from apps.consulta_medica.tests.test_migrar_historial_clinico_legacy import _LEGACY_ROW_BASE, _mock_conn
# Se importa el modulo, no la clase: una clase de test importada aqui la
# descubriria el runner otra vez y repetiria sus tests.
from apps.consulta_medica.tests import test_unified_history

_CONNECT = "apps.authentication.management.commands._legacy_mysql_base.pymysql.connect"
_DENTAL_ROW = test_unified_history.MigrarHistoriaEstomatologiaLegacyTests.ROW


def _run(command, rows, mock_connect):
    mock_connect.return_value = _mock_conn(rows)
    call_command(command, host="x", user="x", password="x", database="x", stdout=StringIO())


class ImportTraceabilityTests(TestCase):
    def setUp(self):
        Ocupaciones.objects.create(name="Contador")
        EdoCivil.objects.create(name="Soltero")

    @patch(_CONNECT)
    def test_his_clinica_guarda_origen_y_texto_original_de_cada_alergia(self, mock_connect):
        row = dict(_LEGACY_ROW_BASE, no_hisclin=12, ds_alergias="Penicilina, mariscos")

        _run("migrar_historial_clinico_legacy", [row], mock_connect)

        history = ClinicalHistory.objects.get(no_exp="EXP-0001")
        self.assertEqual((history.legacy_source_table, history.legacy_source_id), ("his_clinica", 12))
        self.assertEqual(
            dict(Allergy.objects.values_list("substance", "original_text")),
            {"Penicilina": "Penicilina, mariscos", "mariscos": "Penicilina, mariscos"},
        )

    @patch(_CONNECT)
    def test_his_clinicad_sola_deja_su_origen(self, mock_connect):
        _run("migrar_historia_estomatologia_legacy", [dict(_DENTAL_ROW)], mock_connect)

        history = ClinicalHistory.objects.get(no_exp="EXPDENT1")
        self.assertEqual((history.legacy_source_table, history.legacy_source_id), ("his_clinicad", 77))
        self.assertEqual(Allergy.objects.get(no_exp="EXPDENT1").original_text, "Ampicilina")

    @patch(_CONNECT)
    def test_his_clinica_manda_sobre_his_clinicad(self, mock_connect):
        _run("migrar_historia_estomatologia_legacy", [dict(_DENTAL_ROW)], mock_connect)
        _run("migrar_historial_clinico_legacy",
             [dict(_LEGACY_ROW_BASE, no_exp="EXPDENT1", no_hisclin=5)], mock_connect)
        # Otra corrida de estomatologia no le quita el origen a his_clinica.
        _run("migrar_historia_estomatologia_legacy", [dict(_DENTAL_ROW, no_hisclin=78)], mock_connect)

        history = ClinicalHistory.objects.get(no_exp="EXPDENT1")
        self.assertEqual((history.legacy_source_table, history.legacy_source_id), ("his_clinica", 5))


class TraceabilityBackfillMigrationTests(TransactionTestCase):
    """Prueba REAL de la 0049: relleno de lo ya migrado, solo con evidencia."""

    migrate_from = [("consulta_medica", "0048_habito_historial")]
    migrate_to = [("consulta_medica", "0049_trazabilidad_origen_legado")]
    serialized_rollback = True

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _migrate_forward(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps

    def _history(self, no_exp):
        Patient = self.old_apps.get_model("consulta_medica", "Patient")
        ClinicalHistory = self.old_apps.get_model("consulta_medica", "ClinicalHistory")
        patient = Patient.objects.create(no_exp=no_exp, pk_num=0)
        return ClinicalHistory.objects.create(no_exp=no_exp, pk_num=0, patient=patient)

    def test_rellena_solo_lo_que_tiene_evidencia(self):
        Note = self.old_apps.get_model("consulta_medica", "HistoricalNote")
        OldAllergy = self.old_apps.get_model("consulta_medica", "Allergy")

        both = self._history("TRZ1")
        Note.objects.create(clinical_history=both, no_exp="TRZ1", pk_num=0, section="antecedentes",
                            content="x", legacy_ref="his_clinicad:45:ds_antecedentes")
        Note.objects.create(clinical_history=both, no_exp="TRZ1", pk_num=0, section="alergias",
                            content="Penicilina y sulfas", legacy_ref="his_clinica:12:ds_alergias")
        dental_only = self._history("TRZ2")
        Note.objects.create(clinical_history=dental_only, no_exp="TRZ2", pk_num=0, section="padecimiento",
                            content="y", legacy_ref="his_clinicad:46:ds_terapias")
        sires_only = self._history("TRZ3")

        imported = OldAllergy.objects.create(no_exp="TRZ1", pk_num=0, allergy_type_id=9, substance="Penicilina",
                                             severity="M", service_origin_code=1)
        captured = OldAllergy.objects.create(no_exp="TRZ1", pk_num=0, allergy_type_id=9, substance="Sulfas",
                                             severity="M", service_origin_code=1, created_by_id=7)
        unrelated = OldAllergy.objects.create(no_exp="TRZ1", pk_num=0, allergy_type_id=9, substance="Polen",
                                              severity="M", service_origin_code=1)

        apps = self._migrate_forward()
        History = apps.get_model("consulta_medica", "ClinicalHistory")
        Allergy = apps.get_model("consulta_medica", "Allergy")

        origin = lambda pk: History.objects.filter(pk=pk).values_list("legacy_source_table", "legacy_source_id").get()  # noqa: E731
        self.assertEqual(origin(both.pk), ("his_clinica", 12))
        self.assertEqual(origin(dental_only.pk), ("his_clinicad", 46))
        self.assertEqual(origin(sires_only.pk), (None, None))

        self.assertEqual(Allergy.objects.get(pk=imported.pk).original_text, "Penicilina y sulfas")
        # Capturada en SIRES (tiene usuario): no se toca aunque la nota la mencione.
        self.assertIsNone(Allergy.objects.get(pk=captured.pk).original_text)
        # Sin nota que la contenga: no se adivina.
        self.assertIsNone(Allergy.objects.get(pk=unrelated.pk).original_text)
