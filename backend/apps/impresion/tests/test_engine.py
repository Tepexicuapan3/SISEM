import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.impresion import engine
from apps.impresion.errors import PrintError
from apps.impresion.services.safe_fetcher import ASSETS_DIR, is_allowed_url


class SafeFetcherTests(SimpleTestCase):
    def test_allows_file_inside_assets_dir(self):
        url = (ASSETS_DIR / "logo.gif").resolve().as_uri()
        self.assertTrue(is_allowed_url(url))

    def test_allows_data_uri(self):
        self.assertTrue(is_allowed_url("data:image/png;base64,AAAA"))

    def test_blocks_http_and_other_schemes(self):
        for url in (
            "http://169.254.169.254/latest/meta-data",
            "https://example.com/x.png",
            "ftp://example.com/x",
        ):
            self.assertFalse(is_allowed_url(url), url)

    def test_blocks_file_outside_assets_dir(self):
        outside = Path(__file__).resolve().as_uri()
        self.assertFalse(is_allowed_url(outside))

    def test_blocks_path_traversal(self):
        url = (ASSETS_DIR / ".." / ".." / "models.py").as_uri()
        self.assertFalse(is_allowed_url(url))

    def test_blocks_remote_host_file_url(self):
        self.assertFalse(is_allowed_url("file://evil-host/share/x.png"))


class RenderPdfTests(SimpleTestCase):
    def test_weasyprint_error_becomes_print_render_error(self):
        fake = mock.MagicMock()
        fake.HTML.return_value.write_pdf.side_effect = OSError("pango missing")
        with mock.patch.dict(sys.modules, {"weasyprint": fake}), mock.patch.object(
            engine, "render_to_string", return_value="<html></html>"
        ):
            with self.assertRaises(PrintError) as ctx:
                engine.render_pdf("impresion/base.html", {})
        self.assertEqual(ctx.exception.code, "PRINT_RENDER_ERROR")
        self.assertEqual(ctx.exception.status_code, 500)

    def test_missing_weasyprint_becomes_print_render_error(self):
        with mock.patch.dict(sys.modules, {"weasyprint": None}):
            with self.assertRaises(PrintError) as ctx:
                engine.render_pdf("impresion/base.html", {})
        self.assertEqual(ctx.exception.code, "PRINT_RENDER_ERROR")

    def test_success_returns_bytes_and_uses_safe_fetcher(self):
        fake = mock.MagicMock()
        fake.HTML.return_value.write_pdf.return_value = b"%PDF-1.7"
        with mock.patch.dict(sys.modules, {"weasyprint": fake}), mock.patch.object(
            engine, "render_to_string", return_value="<html></html>"
        ):
            out = engine.render_pdf("impresion/base.html", {})
        self.assertEqual(out, b"%PDF-1.7")
        kwargs = fake.HTML.call_args.kwargs
        self.assertIs(kwargs["url_fetcher"], engine.safe_fetcher)
        self.assertEqual(kwargs["base_url"], str(ASSETS_DIR))
