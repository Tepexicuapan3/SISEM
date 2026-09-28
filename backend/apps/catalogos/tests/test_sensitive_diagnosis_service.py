from django.test import TestCase

from apps.catalogos.models import SensitiveCieRange
from apps.catalogos.services.sensitive_diagnosis_service import (
    classify_cie,
    invalidate_cache,
)


class ClassifyCieTests(TestCase):
    """`classify_cie` compara solo el prefijo de CATEGORIA de 3 caracteres
    (ver docstring del servicio) -- estos tests cubren especificamente los
    limites de rango y los subcodigos decimales, que es donde una
    comparacion lexicografica ingenua sobre el codigo completo falla
    (ej. "B24.9" > "B24" como string)."""

    def setUp(self):
        SensitiveCieRange.objects.create(
            code_prefix_start="B20", code_prefix_end="B24",
            category="hiv", required_permission="clinico:diagnosticos_vih:read",
        )
        SensitiveCieRange.objects.create(
            code_prefix_start="F10", code_prefix_end="F19",
            category="substance_use", required_permission="clinico:diagnosticos_sustancias:read",
        )
        SensitiveCieRange.objects.create(
            code_prefix_start="F00", code_prefix_end="F09",
            category="mental_health", required_permission="clinico:diagnosticos_salud_mental:read",
        )
        SensitiveCieRange.objects.create(
            code_prefix_start="F20", code_prefix_end="F99",
            category="mental_health", required_permission="clinico:diagnosticos_salud_mental:read",
        )
        invalidate_cache()

    def tearDown(self):
        invalidate_cache()

    def test_exact_boundary_codes_classify(self):
        self.assertEqual(classify_cie("B20")[0], "hiv")
        self.assertEqual(classify_cie("B24")[0], "hiv")

    def test_decimal_subcode_within_boundary_classifies(self):
        # El caso que rompe una comparacion lexicografica ingenua sobre el
        # codigo completo: "B24.9" > "B24" como string, pero clinicamente
        # SI es parte del bloque B20-B24.
        self.assertEqual(classify_cie("B24.9")[0], "hiv")
        self.assertEqual(classify_cie("B20.0")[0], "hiv")

    def test_codes_just_outside_boundary_do_not_classify(self):
        self.assertIsNone(classify_cie("B19.9"))
        self.assertIsNone(classify_cie("B25.0"))

    def test_substance_use_excluded_from_general_mental_health_block(self):
        result = classify_cie("F19.9")
        self.assertEqual(result[0], "substance_use")
        self.assertNotEqual(result[0], "mental_health")

    def test_mental_health_blocks_around_substance_use_gap(self):
        self.assertEqual(classify_cie("F09.9")[0], "mental_health")
        self.assertEqual(classify_cie("F20.9")[0], "mental_health")
        self.assertEqual(classify_cie("F99.9")[0], "mental_health")

    def test_unrelated_code_returns_none(self):
        self.assertIsNone(classify_cie("I10"))
        self.assertIsNone(classify_cie("J00.0"))

    def test_empty_or_none_code_returns_none(self):
        self.assertIsNone(classify_cie(None))
        self.assertIsNone(classify_cie(""))

    def test_returns_required_permission(self):
        _category, permission = classify_cie("B20")
        self.assertEqual(permission, "clinico:diagnosticos_vih:read")

    def test_inactive_range_is_ignored(self):
        SensitiveCieRange.objects.create(
            code_prefix_start="C00", code_prefix_end="C99",
            category="hiv", required_permission="clinico:diagnosticos_vih:read",
            is_active=False,
        )
        invalidate_cache()
        self.assertIsNone(classify_cie("C50"))
