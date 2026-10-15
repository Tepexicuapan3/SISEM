import base64
from datetime import date
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.consulta_medica.models import Patient
from apps.impresion.services import patient_header as ph
from apps.impresion.services.barcode import code128_data_uri, qr_data_uri


class AgeTests(SimpleTestCase):
    def test_age(self):
        self.assertEqual(ph._age(date(2000, 10, 16), today=date(2026, 10, 15)), "25")
        self.assertEqual(ph._age(date(2000, 10, 15), today=date(2026, 10, 15)), "26")
        self.assertEqual(ph._age(None), "")


class PatientHeaderChainTests(TestCase):
    def test_uses_cns_paciente_first_and_skips_sermed(self):
        Patient.objects.create(
            no_exp="100", pk_num=0, first_name="ANA", paternal_surname="LOPEZ",
            maternal_surname="DIAZ", birth_date=date(1990, 1, 1),
        )
        lookup = mock.Mock()
        h = ph.get_patient_header("100", 0, "NOMBRE VISITA", sermed_lookup=lookup)
        self.assertEqual(h["source"], ph.SOURCE_PATIENT)
        self.assertEqual(h["full_name"], "ANA LOPEZ DIAZ")
        lookup.assert_not_called()

    def test_falls_back_to_sermed_titular(self):
        lookup = mock.Mock(return_value={
            "empleados": [{"DS_PATERNO": "PEREZ", "DS_MATERNO": "RUIZ", "DS_NOMBRE": "JUAN", "EDAD": 40}],
            "familiares": [],
        })
        h = ph.get_patient_header("200", 0, "X", sermed_lookup=lookup)
        self.assertEqual(h["source"], ph.SOURCE_SERMED)
        self.assertEqual(h["full_name"], "JUAN PEREZ RUIZ")
        self.assertEqual(h["age"], "40")

    def test_falls_back_to_sermed_familiar_by_pk_num(self):
        lookup = mock.Mock(return_value={
            "empleados": [{"DS_NOMBRE": "TITULAR"}],
            "familiares": [{"PK_NUM": 2, "DS_PATERNO": "G", "DS_MATERNO": "H", "DS_NOMBRE": "HIJO"}],
        })
        h = ph.get_patient_header("200", 2, sermed_lookup=lookup)
        self.assertEqual(h["full_name"], "HIJO G H")

    def test_falls_back_to_visit_name_when_sermed_empty_or_fails(self):
        for lookup in (
            mock.Mock(return_value={"empleados": [], "familiares": []}),
            mock.Mock(side_effect=RuntimeError("oracle down")),
        ):
            h = ph.get_patient_header("300", 0, "  NOMBRE VISITA ", sermed_lookup=lookup)
            self.assertEqual(h["source"], ph.SOURCE_VISIT)
            self.assertEqual(h["full_name"], "NOMBRE VISITA")

    def test_nothing_resolved(self):
        lookup = mock.Mock(return_value={})
        h = ph.get_patient_header("400", 0, "", sermed_lookup=lookup)
        self.assertIsNone(h["source"])
        self.assertEqual(h["full_name"], "")

    def test_no_oracle_dml_only_buscar_expediente_select(self):
        # El unico acceso a SERMED es buscar_expediente (SELECT). Se verifica que
        # el modulo no importa nada que escriba.
        src = open(ph.__file__, encoding="utf-8").read().lower()
        for word in ("insert ", "update ", "delete ", ".save(", ".create("):
            self.assertNotIn(word, src)


class BarcodeTests(SimpleTestCase):
    def test_code128_is_svg_data_uri(self):
        uri = code128_data_uri("RX-2026-15")
        self.assertTrue(uri.startswith("data:image/svg+xml;base64,"))
        svg = base64.b64decode(uri.split(",", 1)[1]).decode()
        self.assertIn("<svg", svg)
        self.assertIn("<rect", svg)

    def test_code128_empty_raises(self):
        with self.assertRaises(ValueError):
            code128_data_uri("")

    def test_qr_is_svg_data_uri(self):
        uri = qr_data_uri("https://example.org/x")
        svg = base64.b64decode(uri.split(",", 1)[1]).decode()
        self.assertIn("<svg", svg)
