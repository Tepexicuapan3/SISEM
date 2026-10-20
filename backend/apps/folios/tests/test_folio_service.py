import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.test import TestCase

from apps.folios.models import FolioCounter, FolioType
from apps.folios.services.folio_service import format_folio, next_folio

MX = ZoneInfo("America/Mexico_City")


class FolioServiceTests(TestCase):
    def test_format_has_no_patient_data(self):
        self.assertEqual(format_folio(FolioType.LICENCIA, 2026, 123), "LIC-2026-000123")

    def test_sequence_increments_per_type(self):
        when = datetime.datetime(2026, 5, 1, 10, 0, tzinfo=MX)
        self.assertEqual(next_folio(FolioType.PASE, when=when), "REF-2026-000001")
        self.assertEqual(next_folio(FolioType.PASE, when=when), "REF-2026-000002")
        self.assertEqual(next_folio(FolioType.LICENCIA, when=when), "LIC-2026-000001")

    def test_restarts_each_year(self):
        self.assertEqual(
            next_folio(FolioType.CIRUGIA, when=datetime.datetime(2026, 12, 31, 23, 0, tzinfo=MX)),
            "CIR-2026-000001",
        )
        self.assertEqual(
            next_folio(FolioType.CIRUGIA, when=datetime.datetime(2027, 1, 1, 0, 5, tzinfo=MX)),
            "CIR-2027-000001",
        )

    def test_year_uses_local_time(self):
        # 2027-01-01 03:00 UTC sigue siendo 2026 en Ciudad de Mexico.
        utc = datetime.datetime(2027, 1, 1, 3, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(next_folio(FolioType.AMBULANCIA, when=utc), "AMB-2026-000001")

    def test_rolled_back_creation_leaves_no_gap(self):
        when = datetime.datetime(2026, 3, 1, tzinfo=MX)
        try:
            with transaction.atomic():
                next_folio(FolioType.LICENCIA, when=when)
                raise RuntimeError("alta fallida")
        except RuntimeError:
            pass
        self.assertEqual(next_folio(FolioType.LICENCIA, when=when), "LIC-2026-000001")

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            next_folio("XXX")
        self.assertFalse(FolioCounter.objects.exists())
