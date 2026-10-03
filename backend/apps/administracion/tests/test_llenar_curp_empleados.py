from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from apps.administracion.services.curp_empleados_service import llenar_curp_empleados
from apps.consulta_medica.models import LegacyMigrationRun


class _FakeOracleCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.executed = []
        self.closed = False

    def execute(self, sql, params=None):
        self.executed.append(sql)

    def fetchmany(self, size):
        lote, self._rows = self._rows[:size], self._rows[size:]
        return lote

    def close(self):
        self.closed = True


class _FakeOracleConn:
    def __init__(self, rows):
        self.cursor_obj = _FakeOracleCursor(rows)

    def cursor(self):
        return self.cursor_obj


class LlenarCurpEmpleadosServiceTests(TestCase):
    """La replica vive en la conexion 'expedientes', que no existe en tests:
    se crea cat_empleados en 'default' y se usa alias='default'."""

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS cat_empleados ("
                " no_exp varchar(20) PRIMARY KEY, curp varchar(18), cd_sexo varchar(1))"
            )
            cursor.executemany(
                "INSERT INTO cat_empleados (no_exp, curp, cd_sexo) VALUES (%s, NULL, NULL)",
                [("1001",), ("1002",), ("1003",)],
            )

    def _replica(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT no_exp, curp, cd_sexo FROM cat_empleados ORDER BY no_exp")
            return {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    def _llenar(self, rows, **kwargs):
        oracle = _FakeOracleConn(rows)
        conteos = llenar_curp_empleados(oracle, alias="default", **kwargs)
        return conteos, oracle

    def test_copia_curp_y_sexo_tal_cual_vienen_de_oracle(self):
        conteos, _ = self._llenar([
            (1001, "AEGH550716HDFRRM00", "M"),
            (Decimal("1002"), "SIN CURP", "F"),
            (1003.0, None, "M"),
        ])

        self.assertEqual(self._replica(), {
            "1001": ("AEGH550716HDFRRM00", "M"),
            "1002": ("SIN CURP", "F"),
            "1003": (None, "M"),
        })
        self.assertEqual(conteos["actualizados"], 3)

    def test_es_idempotente(self):
        rows = [(1001, "AEGH550716HDFRRM00", "M")]
        self._llenar(rows)

        conteos, _ = self._llenar(rows)

        self.assertEqual(conteos["actualizados"], 0)
        self.assertEqual(conteos["sin_cambio"], 1)

    def test_dry_run_no_escribe(self):
        conteos, _ = self._llenar([(1001, "AEGH550716HDFRRM00", "M")], dry_run=True)

        self.assertEqual(conteos["actualizados"], 1)
        self.assertEqual(self._replica()["1001"], (None, None))

    def test_no_inserta_empleados_que_no_estan_en_la_replica(self):
        conteos, _ = self._llenar([(9999, "AEGH550716HDFRRM00", "M")])

        self.assertEqual(conteos["no_en_replica"], 1)
        self.assertNotIn("9999", self._replica())

    def test_procesa_por_lotes(self):
        conteos, _ = self._llenar(
            [(1001, "A", "M"), (1002, "B", "F"), (1003, "C", "M")],
            batch_size=1,
        )

        self.assertEqual(conteos["leidos"], 3)
        self.assertEqual(conteos["actualizados"], 3)

    def test_a_oracle_solo_se_le_hace_select(self):
        _, oracle = self._llenar([(1001, "A", "M")])

        for sql in oracle.cursor_obj.executed:
            self.assertTrue(sql.strip().upper().startswith("SELECT"), sql)
        self.assertTrue(oracle.cursor_obj.closed)


class LlenarCurpEmpleadosCommandTests(TestCase):
    _BASE = "apps.administracion.management.commands.llenar_curp_empleados"

    def test_registra_la_ejecucion_en_la_bitacora_de_migracion(self):
        oracle = MagicMock()
        conteos = {"leidos": 5, "actualizados": 3, "sin_cambio": 1, "no_en_replica": 1}
        with patch(f"{self._BASE}.obtener_conexion_oracle", return_value=oracle), \
             patch(f"{self._BASE}.llenar_curp_empleados", return_value=conteos) as llenar:
            call_command("llenar_curp_empleados", "--dry-run", "--operador", "tester", stdout=StringIO())

        llenar.assert_called_once_with(oracle, dry_run=True, batch_size=500)
        oracle.close.assert_called_once()
        run = LegacyMigrationRun.objects.get(command="llenar_curp_empleados")
        self.assertEqual(run.status, LegacyMigrationRun.Status.OK)
        self.assertTrue(run.dry_run)
        self.assertEqual(run.rows_read, 5)
        self.assertIn("Actualizados: 3", run.summary)

    def test_si_oracle_no_responde_la_ejecucion_queda_fallida(self):
        with patch(f"{self._BASE}.obtener_conexion_oracle", side_effect=RuntimeError("sin red")):
            with self.assertRaises(Exception):
                call_command("llenar_curp_empleados", stdout=StringIO())

        run = LegacyMigrationRun.objects.get(command="llenar_curp_empleados")
        self.assertEqual(run.status, LegacyMigrationRun.Status.FAILED)
        self.assertIn("sin red", run.summary)
