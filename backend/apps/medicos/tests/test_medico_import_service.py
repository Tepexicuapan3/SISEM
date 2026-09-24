"""Cobertura paramétrica de `normalize_legacy_cd` -- la función pública que
`medico_import_service.parse_and_validate` usa para limpiar la columna
"ID del Médico" del Excel, y que la futura migración de
`det_cirugia.cd_medico` va a reusar (ver Engram, topic_key
sdd/medicos-legacy-field-bulk-import/design, "Decisión 4"). No toca la BD
-- `SimpleTestCase`, igual que `test_permission_dependencies_service.py`."""

from django.test import SimpleTestCase

from apps.medicos.services.medico_import_service import normalize_legacy_cd


class NormalizeLegacyCdTests(SimpleTestCase):
    def test_sentinelas_se_normalizan_a_none(self):
        sentinelas = [
            "", "  ", "S/C", "s/c", "SC", "sc", "S\\C", "S / C", " S / C ",
            "SN", "sn", "S/N", "N/A", "n/a", "NA", "na", "-", "--",
            "NULL", "null", "NONE", "none", "0", "nan", "NaN",
        ]
        for raw in sentinelas:
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_legacy_cd(raw))

    def test_none_se_normaliza_a_none(self):
        self.assertIsNone(normalize_legacy_cd(None))

    def test_claves_reales_no_se_tratan_como_sentinelas(self):
        """E00000/H99999 son claves REALES del legado, no basura -- no deben
        normalizarse a None (decisión confirmada, no reabrir)."""
        for raw, expected in [
            ("E00000", "E00000"),
            ("H99999", "H99999"),
            ("e00000", "E00000"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_legacy_cd(raw), expected)

    def test_normaliza_a_mayusculas_y_colapsa_espacios(self):
        self.assertEqual(normalize_legacy_cd("  a1b2c3  "), "A1B2C3")
        self.assertEqual(normalize_legacy_cd("a1  b2"), "A1 B2")

    def test_trunca_a_10_caracteres(self):
        self.assertEqual(normalize_legacy_cd("ABCDEFGHIJKLMNOP"), "ABCDEFGHIJ")

    def test_valor_numerico_distinto_de_cero_no_es_sentinela(self):
        # "0" es sentinela explicito, pero otros numeros son claves validas.
        self.assertEqual(normalize_legacy_cd("12345"), "12345")
        self.assertEqual(normalize_legacy_cd(12345), "12345")
