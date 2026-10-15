from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from apps.impresion.config import validate_ficha_engine


class FichaEngineConfigTests(SimpleTestCase):
    def test_valid_values(self):
        self.assertEqual(validate_ficha_engine("weasy"), "weasy")
        self.assertEqual(validate_ficha_engine(" DOCX "), "docx")

    def test_invalid_value_raises(self):
        for bad in ("pdf", "", None, "libreoffice"):
            with self.assertRaises(ImproperlyConfigured):
                validate_ficha_engine(bad)

    def test_settings_defaults(self):
        self.assertIn(settings.FICHA_ENGINE, ("weasy", "docx"))
        self.assertEqual(settings.PRINT_MAX_CONCURRENCY, 2)
        self.assertEqual(settings.PRINT_QUEUE_TIMEOUT_S, 15)
        self.assertIn("apps.impresion", settings.INSTALLED_APPS)
