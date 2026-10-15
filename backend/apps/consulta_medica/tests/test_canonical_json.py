"""canonical_json + SHA-256 (S35, S36) y reconciliacion RH de solo lectura (5.5)."""
import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.consulta_medica.services.canonical_json import (
    canonical_bytes,
    canonical_json,
    sha256_hex,
)
from apps.consulta_medica.services.medical_leave_rh_reconciliation import find_folios_in_rh


class CanonicalJsonTests(SimpleTestCase):
    def test_orden_de_claves_no_afecta_el_resultado(self):
        a = {"b": 1, "a": {"y": 2, "x": 1}}
        b = {"a": {"x": 1, "y": 2}, "b": 1}
        self.assertEqual(canonical_json(a), canonical_json(b))
        self.assertEqual(canonical_json(a), '{"a":{"x":1,"y":2},"b":1}')

    def test_las_listas_conservan_su_orden(self):
        self.assertEqual(canonical_json({"l": [3, 1, 2]}), '{"l":[3,1,2]}')

    def test_decimal_fecha_y_datetime(self):
        obj = {
            "d": Decimal("1.50"), "e": Decimal("1E+2"), "f": date(2026, 1, 5),
            "t": datetime(2026, 1, 5, 12, 30, 1, 5, tzinfo=timezone.utc),
            "n": None, "ok": True,
        }
        self.assertEqual(
            canonical_json(obj),
            '{"d":"1.50","e":"100","f":"2026-01-05",'
            '"n":null,"ok":true,"t":"2026-01-05T12:30:01.000005Z"}',
        )

    def test_datetime_con_zona_se_normaliza_a_utc(self):
        tz = timezone(timedelta(hours=-6))
        moment = datetime(2026, 1, 5, 6, 0, 0, tzinfo=tz)
        self.assertEqual(canonical_json(moment), '"2026-01-05T12:00:00.000000Z"')

    def test_unicode_sin_escapar(self):
        self.assertEqual(canonical_json({"k": "Atención"}), '{"k":"Atención"}')

    def test_float_no_soportado(self):
        with self.assertRaises(TypeError):
            canonical_json({"x": 1.5})

    def test_tipo_desconocido(self):
        with self.assertRaises(TypeError):
            canonical_json({"x": object()})

    def test_mismo_contenido_mismo_hash_y_hash_es_sha256_del_texto(self):
        obj = {"schema": "cancelacion-nota/v1", "items": [{"id": 1}]}
        text = canonical_json(obj)
        self.assertEqual(sha256_hex(text), sha256_hex(canonical_json(dict(obj))))
        self.assertEqual(sha256_hex(text), hashlib.sha256(text.encode("utf-8")).hexdigest())
        self.assertEqual(len(sha256_hex(text)), 64)
        self.assertEqual(canonical_bytes(obj), text.encode("utf-8"))

    def test_cambio_minimo_cambia_el_hash(self):
        self.assertNotEqual(
            sha256_hex(canonical_json({"a": 1})), sha256_hex(canonical_json({"a": 2})),
        )


class RhReconciliationTests(SimpleTestCase):
    def test_sin_folios_no_consulta(self):
        with patch(
            "apps.consulta_medica.services.medical_leave_rh_reconciliation.connections"
        ) as conns:
            self.assertEqual(find_folios_in_rh([]), set())
            self.assertEqual(find_folios_in_rh([None, ""]), set())
            conns.__getitem__.assert_not_called()

    def test_select_parametrizado_y_devuelve_los_encontrados(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("F1 ",)]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch(
            "apps.consulta_medica.services.medical_leave_rh_reconciliation.connections",
            {"expedientes": connection},
        ):
            found = find_folios_in_rh(["F1", "F2", "F1"])
        self.assertEqual(found, {"F1"})
        sql, params = cursor.execute.call_args.args
        self.assertTrue(sql.startswith("SELECT no_folio FROM dnt_licencias_medicas WHERE"))
        self.assertEqual(sql.count("%s"), 2)
        self.assertEqual(params, ["F1", "F2"])
        self.assertNotIn("F1", sql)  # valores nunca interpolados

    def test_alias_inexistente_no_bloquea(self):
        with patch(
            "apps.consulta_medica.services.medical_leave_rh_reconciliation.connections", {},
        ):
            self.assertEqual(find_folios_in_rh(["LIC-1"]), set())

    def test_tabla_ausente_o_error_de_bd_no_bloquea(self):
        connection = MagicMock()
        connection.cursor.side_effect = RuntimeError('relation "dnt_licencias_medicas" does not exist')
        with patch(
            "apps.consulta_medica.services.medical_leave_rh_reconciliation.connections",
            {"expedientes": connection},
        ):
            self.assertEqual(find_folios_in_rh(["LIC-1"]), set())

    def test_en_tests_sin_alias_real_tampoco_bloquea(self):
        # Con la configuracion de test (solo sqlite 'default') el alias no existe.
        self.assertEqual(find_folios_in_rh(["LIC-1"]), set())
