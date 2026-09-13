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
from apps.consulta_medica.models import ClinicalHistory

_LEGACY_ROW_BASE = {
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

        history = ClinicalHistory.objects.get(no_exp="EXP-0001", pk_num=0)
        self.assertEqual(history.occupation_id, self.ocupacion.id)
        self.assertEqual(history.marital_status_id, self.edocivil.id)
        self.assertIsNone(history.religion_id)
        self.assertEqual(history.phone, "5555555555")
        self.assertEqual(history.current_illness, "Dolor de cabeza")
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
        history = ClinicalHistory.objects.get(no_exp="EXP-0001", pk_num=0)
        self.assertEqual(history.current_illness, "Actualizado")
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

        history = ClinicalHistory.objects.get(no_exp="EXP-0001", pk_num=0)
        self.assertIsNone(history.occupation_id)
        self.assertIn("Ocupacion Que No Existe En SISEM", out.getvalue())

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_preserves_legacy_fecha_as_created_at(self, mock_connect):
        row = dict(_LEGACY_ROW_BASE)
        row["fe_hisclin"] = datetime.datetime(2019, 3, 15, 10, 0, 0)
        mock_connect.return_value = _mock_conn([row])

        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x", database="x")

        history = ClinicalHistory.objects.get(no_exp="EXP-0001", pk_num=0)
        self.assertEqual(str(history.created_at.date()), "2019-03-15")

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
