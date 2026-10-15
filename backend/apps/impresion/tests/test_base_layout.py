import tempfile
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from apps.impresion.services.branding import DEFAULT_LOGO, resolve_logo_uri
from apps.impresion.services.watermark import resolve_watermarks


class WatermarkMatrixTests(SimpleTestCase):
    def labels(self, **kw):
        return [m.label for m in resolve_watermarks(**kw)]

    def test_original_has_none(self):
        self.assertEqual(self.labels(is_cancelled=False, copy_number=1), [])

    def test_reprint_adds_reimpresion(self):
        self.assertEqual(self.labels(is_cancelled=False, copy_number=2), ["REIMPRESIÓN"])

    def test_reprint_without_flag_has_none(self):
        self.assertEqual(
            self.labels(is_cancelled=False, copy_number=3, watermark_on_reprint=False), []
        )

    def test_cancelled_first_copy(self):
        self.assertEqual(self.labels(is_cancelled=True, copy_number=1), ["CANCELADA"])

    def test_cancelled_reprint_shows_both_cancelada_first(self):
        self.assertEqual(
            self.labels(is_cancelled=True, copy_number=2), ["CANCELADA", "REIMPRESIÓN"]
        )

    def test_cancelled_reprint_flag_off_only_cancelada(self):
        self.assertEqual(
            self.labels(is_cancelled=True, copy_number=2, watermark_on_reprint=False),
            ["CANCELADA"],
        )


class LogoResolutionTests(SimpleTestCase):
    def test_center_logo_used_when_present(self):
        with tempfile.TemporaryDirectory() as d:
            logo = Path(d) / "7a.gif"
            logo.write_bytes(b"GIF89a")
            self.assertEqual(resolve_logo_uri(7, logos_dir=Path(d)), logo.resolve().as_uri())

    def test_fallback_when_center_has_no_logo(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                resolve_logo_uri(99, logos_dir=Path(d)), DEFAULT_LOGO.resolve().as_uri()
            )

    def test_fallback_when_center_code_is_none(self):
        self.assertEqual(resolve_logo_uri(None), DEFAULT_LOGO.resolve().as_uri())

    def test_default_logo_exists(self):
        self.assertTrue(DEFAULT_LOGO.is_file())


class BaseTemplateTests(SimpleTestCase):
    def render(self, **extra):
        ctx = {
            "institution_name": "Institucion X",
            "doc_title": "Ficha",
            "logo_uri": "file:///logo.svg",
            "printed_by": "jperez",
            "printed_at": "15/10/2026 10:00",
            "copy_number": 1,
            "watermarks": [],
        }
        ctx.update(extra)
        return render_to_string("impresion/base.html", ctx)

    def test_header_and_footer(self):
        html = self.render()
        for text in ("Institucion X", "jperez", "15/10/2026 10:00", "Impresión 1", "logo.svg"):
            self.assertIn(text, html)
        self.assertNotIn("CANCELADA", html)

    def test_watermarks_rendered(self):
        marks = resolve_watermarks(is_cancelled=True, copy_number=2)
        html = self.render(watermarks=marks, copy_number=2)
        self.assertIn("CANCELADA", html)
        self.assertIn("REIMPRESIÓN", html)

    def test_user_data_is_escaped(self):
        html = self.render(printed_by="<script>x</script>")
        self.assertNotIn("<script>x</script>", html)
