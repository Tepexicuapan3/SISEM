from types import SimpleNamespace
from unittest import mock

from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Medicamentos
from apps.consulta_medica.impresion.nota import build_nota_context
from apps.consulta_medica.impresion.receta import (
    ROWS_PER_SHEET,
    SHEET_TEMPLATE_CONTROLADO,
    SHEET_TEMPLATE_NORMAL,
    _center_address,
    _date_boxes,
    _drug_label,
    _general_indications,
    build_receta_context,
    build_sheets,
)
from apps.consulta_medica.models import (
    PrescriptionAuthorization,
    VisitConsultation,
    VisitDiagnosis,
    VisitPrescription,
    VisitPrescriptionItem,
)
from apps.impresion.errors import PrintError
from apps.impresion.models import PrintLog
from apps.impresion.registry import REGISTRY
from apps.impresion.uses_case import print_document_usecase as uc
from apps.recepcion.models import Visit
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave

HEADER = "apps.consulta_medica.impresion.common.get_patient_header"
RENDER = "apps.impresion.uses_case.print_document_usecase.engine.render_pdf"
CLASSIFY = "apps.consulta_medica.services.diagnosis_redaction_service.classify_cie"


def _header(source="cns_paciente"):
    return {
        "no_exp": "E1", "pk_num": 0, "paternal_surname": "Perez", "maternal_surname": "Lopez",
        "first_name": "Juan", "full_name": "Juan Perez Lopez", "age": "40",
        "birth_date": "01/01/1985", "sex": "M", "source": source,
    }


def _vih_only(code):
    return ("VIH", "clinico:diagnosticos_vih:read") if (code or "").upper().startswith("B24") else None


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.doctor = SyUsuario.objects.create(usuario="dr_print", clave_hash="x")
        cls.cie = CatCies.objects.create(code="A090", description="GASTROENTERITIS", version="CIE-10", is_active=True)
        cls.cie_vih = CatCies.objects.create(code="B24", description="VIH", version="CIE-10", is_active=True)
        cls.med = Medicamentos.objects.create(name="Paracetamol 500mg", generic_name="Paracetamol")
        cls.med_ctrl = Medicamentos.objects.create(name="Clonazepam 2mg", is_controlled=True)

    def _visit(self, folio, status="cerrada"):
        return Visit.objects.create(
            folio=folio, patient=_paciente_de_llave("E1", 0), arrival_type="walk_in",
            service_type="medicina_general", status=status, nombre_paciente="Visit Name",
        )

    def _consultation(self, visit, **kw):
        data = dict(
            id_visit=visit, doctor=self.doctor, primary_diagnosis="Gastroenteritis aguda",
            cie=self.cie, final_note="Reposo e hidratacion", subjective="Dolor abdominal",
        )
        data.update(kw)
        return VisitConsultation.objects.create(**data)

    def _prescription(self, visit, meds, folio="RX-2026-1"):
        rx = VisitPrescription.objects.create(id_visit=visit, items=["Tomar liquidos"], folio=folio)
        for med in meds:
            VisitPrescriptionItem.objects.create(
                prescription=rx, medication=med, dose="1 tab", indications="Cada 8 h", quantity=10,
            )
        return rx


NORMAL = VisitPrescription.PrescriptionType.NORMAL
TRANSCRIPTION = VisitPrescription.PrescriptionType.TRANSCRIPTION


class RecetaSheetsTests(TestCase):
    def test_no_controlled_two_sheets(self):
        sheets = build_sheets([{"is_controlled": False}], NORMAL)
        self.assertEqual([s["label"] for s in sheets], ["ORIGINAL", "COPIA"])

    def test_controlled_adds_sheet_with_only_controlled_items(self):
        rows = [{"is_controlled": False, "name": "a"}, {"is_controlled": True, "name": "b"}]
        sheets = build_sheets(rows, NORMAL)
        self.assertEqual([s["label"] for s in sheets], ["ORIGINAL", "COPIA", "CONTROLADO"])
        self.assertEqual([r["name"] for r in sheets[2]["items"]], ["b"])

    def test_original_and_copy_use_normal_design(self):
        sheets = build_sheets([{"is_controlled": False}], NORMAL)
        self.assertEqual({s["template"] for s in sheets}, {SHEET_TEMPLATE_NORMAL})

    def test_transcription_uses_normal_design_until_it_has_its_own(self):
        sheets = build_sheets([{"is_controlled": False}], TRANSCRIPTION)
        self.assertEqual(sheets[0]["template"], SHEET_TEMPLATE_NORMAL)

    def test_controlled_sheet_uses_controlled_design(self):
        sheets = build_sheets([{"is_controlled": True}], NORMAL)
        self.assertEqual(sheets[2]["template"], SHEET_TEMPLATE_CONTROLADO)

    def test_only_copy_carries_stamp(self):
        sheets = build_sheets([{"is_controlled": True}], NORMAL)
        self.assertEqual([s["stamp"] for s in sheets], [None, "COPIA", None])

    # A2 (receta-a5-cumplimiento): lo que no cabe en una hoja sigue en otra.
    def test_rows_that_fit_use_one_sheet_per_label(self):
        rows = [{"is_controlled": False, "name": str(i)} for i in range(ROWS_PER_SHEET)]
        sheets = build_sheets(rows, NORMAL)
        self.assertEqual([(s["label"], s["page"], s["pages"]) for s in sheets], [("ORIGINAL", 1, 1), ("COPIA", 1, 1)])

    def test_overflow_adds_continuation_sheets(self):
        rows = [{"is_controlled": False, "name": str(i)} for i in range(2 * ROWS_PER_SHEET + 1)]
        sheets = build_sheets(rows, NORMAL)
        self.assertEqual(
            [(s["label"], s["page"], s["pages"]) for s in sheets],
            [("ORIGINAL", 1, 3), ("ORIGINAL", 2, 3), ("ORIGINAL", 3, 3),
             ("COPIA", 1, 3), ("COPIA", 2, 3), ("COPIA", 3, 3)],
        )
        self.assertEqual([r["name"] for s in sheets[:3] for r in s["items"]], [r["name"] for r in rows])
        self.assertEqual({s["stamp"] for s in sheets[3:]}, {"COPIA"})

    def test_numbering_continues_across_sheets(self):
        rows = [{"is_controlled": False, "name": str(i)} for i in range(ROWS_PER_SHEET + 1)]
        second = build_sheets(rows, NORMAL)[1]
        self.assertEqual(second["first_number"], ROWS_PER_SHEET + 1)

    def test_only_last_sheet_of_each_label_is_last(self):
        rows = [{"is_controlled": False, "name": str(i)} for i in range(ROWS_PER_SHEET + 1)]
        self.assertEqual([s["last"] for s in build_sheets(rows, NORMAL)], [False, True, False, True])

    def test_controlled_sheet_splits_only_controlled_rows(self):
        rows = [{"is_controlled": True, "name": str(i)} for i in range(ROWS_PER_SHEET + 1)]
        rows.append({"is_controlled": False, "name": "x"})
        controlled = [s for s in build_sheets(rows, NORMAL) if s["label"] == "CONTROLADO"]
        self.assertEqual([(s["page"], s["pages"]) for s in controlled], [(1, 2), (2, 2)])
        self.assertNotIn("x", [r["name"] for s in controlled for r in s["items"]])

    def test_every_sheet_template_exists(self):
        for template in (SHEET_TEMPLATE_NORMAL, SHEET_TEMPLATE_CONTROLADO):
            get_template(template)


class RecetaContextHelpersTests(TestCase):
    def test_date_boxes_splits_day_month_year(self):
        self.assertEqual(_date_boxes("07/07/1959"), {"d": "07", "m": "07", "y": "1959"})

    def test_date_boxes_empty_or_invalid_gives_empty_boxes(self):
        for value in ("", None, "1959-07-07"):
            with self.subTest(value=value):
                self.assertEqual(_date_boxes(value), {"d": "", "m": "", "y": ""})

    def test_center_address_skips_empty_parts(self):
        center = SimpleNamespace(
            address="AV. CHAPULTEPEC 98", neighborhood="ROMA NTE.", municipality="", postal_code="06700",
            city="CIUDAD DE MEXICO", state=None,
        )
        self.assertEqual(
            _center_address(center),
            {"line1": "AV. CHAPULTEPEC 98, ROMA NTE., 06700", "line2": "CIUDAD DE MEXICO"},
        )

    def test_center_address_without_center(self):
        self.assertEqual(_center_address(None), {"line1": "", "line2": ""})

    def test_general_indications_cleans_texts(self):
        self.assertEqual(_general_indications(["  Tomar liquidos ", "", "  ", "Reposo"]), ["Tomar liquidos", "Reposo"])

    def test_general_indications_not_a_list(self):
        for value in (None, {}, "texto"):
            with self.subTest(value=value):
                self.assertEqual(_general_indications(value), [])

    # RIS art. 31: en el sector publico se prescribe por denominacion generica.
    def test_drug_label_puts_generic_first(self):
        row = {"name": "Clonazepam 2mg", "generic_name": "Clonazepam", "presentation": "Tableta"}
        self.assertEqual(_drug_label(row), {"primary": "Clonazepam", "secondary": "Clonazepam 2mg. Tableta"})

    def test_drug_label_without_generic_uses_name(self):
        row = {"name": "Vitamina D 800 UI", "generic_name": "", "presentation": "Tableta"}
        self.assertEqual(_drug_label(row), {"primary": "Vitamina D 800 UI", "secondary": "Tableta"})

    def test_drug_label_generic_equal_to_name_is_not_repeated(self):
        row = {"name": "PARACETAMOL", "generic_name": "Paracetamol", "presentation": ""}
        self.assertEqual(_drug_label(row), {"primary": "Paracetamol", "secondary": ""})


_BLOCKS = "consulta_medica/impresion/receta/bloques"


class RecetaBlocksTests(TestCase):
    def test_signature_box_is_left_blank_for_the_autograph(self):
        # RIS art. 29: firma autografa; la casilla no se llena con el nombre impreso.
        html = render_to_string(f"{_BLOCKS}/_firma.html", {"doctor": {"name": "DRA. ROSA RUIZ", "cedula": "123"}})
        self.assertEqual(html.count("DRA. ROSA RUIZ"), 1)

    def test_header_prints_issue_time(self):
        html = render_to_string(
            f"{_BLOCKS}/_encabezado.html",
            {"sheet": {"label": "ORIGINAL"}, "issued_date": "26/03/2024", "issued_time": "11:31"},
        )
        self.assertIn("26/03/2024 11:31", html)

    def test_data_block_prints_clues(self):
        html = render_to_string(f"{_BLOCKS}/_datos.html", {"clues": "DFSTC000123", "issued": {}, "birth": {}})
        self.assertIn("DFSTC000123", html)

    def test_data_block_prints_age_and_sex(self):
        html = render_to_string(
            f"{_BLOCKS}/_datos.html", {"patient": {"age": "67", "sex": "F"}, "issued": {}, "birth": {}},
        )
        for text in ("Edad", "Sexo", '<span class="val">67</span>', '<span class="val">F</span>'):
            self.assertIn(text, html)

    def test_data_block_hides_clues_label_without_value(self):
        html = render_to_string(f"{_BLOCKS}/_datos.html", {"clues": "", "issued": {}, "birth": {}})
        self.assertNotIn("CLUES", html)

    def test_header_shows_sheet_number_only_with_continuation(self):
        render = lambda sheet: render_to_string(f"{_BLOCKS}/_encabezado.html", {"sheet": sheet})
        self.assertIn("Hoja 2 de 3", render({"label": "ORIGINAL", "page": 2, "pages": 3}))
        self.assertNotIn("Hoja", render({"label": "ORIGINAL", "page": 1, "pages": 1}))

    def test_medication_numbering_continues_on_next_sheet(self):
        item = {"label": {"primary": "X", "secondary": ""}, "quantity": 1}
        html = render_to_string(
            f"{_BLOCKS}/_medicamentos.html", {"sheet": {"items": [item, item], "first_number": 6}},
        )
        self.assertIn('<td class="num">6</td>', html)
        self.assertIn('<td class="num">7</td>', html)

    def test_general_indications_only_on_last_sheet(self):
        ctx = {"general_indications": ["Tomar liquidos"], "issued": {}, "birth": {}}
        sheet = "consulta_medica/impresion/receta/hojas/normal.html"
        self.assertNotIn("Tomar liquidos", render_to_string(sheet, dict(ctx, sheet={"last": False, "items": []})))
        self.assertIn("Tomar liquidos", render_to_string(sheet, dict(ctx, sheet={"last": True, "items": []})))

    def test_medication_block_shows_generic_before_name(self):
        item = {"label": {"primary": "Clonazepam", "secondary": "Clonazepam 2mg. Tableta"}, "quantity": 1}
        html = render_to_string(f"{_BLOCKS}/_medicamentos.html", {"sheet": {"items": [item], "first_number": 1}})
        self.assertLess(html.index("Clonazepam<"), html.index("Clonazepam 2mg. Tableta"))


class RecetaBuilderTests(_Base):
    def _build(self, visit):
        with mock.patch(HEADER, return_value=_header()):
            return build_receta_context(visit.id_visit, self.doctor)

    def test_closed_consultation_builds_context(self):
        visit = self._visit("V-R1")
        self._consultation(visit)
        self._prescription(visit, [self.med, self.med_ctrl])
        pctx = self._build(visit)
        self.assertEqual(pctx.folio, "RX-2026-1")
        self.assertEqual(pctx.filename, "receta_RX-2026-1.pdf")
        self.assertFalse(pctx.is_cancelled)
        self.assertEqual([s["label"] for s in pctx.context["sheets"]], ["ORIGINAL", "COPIA", "CONTROLADO"])
        self.assertEqual(pctx.context["general_indications"], ["Tomar liquidos"])

    def test_context_has_form_boxes_and_barcode(self):
        visit = self._visit("V-R9")
        self._consultation(visit)
        self._prescription(visit, [self.med], folio="RX-2026-9")
        ctx = self._build(visit).context
        self.assertEqual(ctx["birth"], {"d": "01", "m": "01", "y": "1985"})
        self.assertEqual(set(ctx["issued"]), {"d", "m", "y"})
        self.assertTrue(ctx["issued"]["y"])
        self.assertEqual(ctx["center_address"], {"line1": "", "line2": ""})
        self.assertTrue(ctx["barcode_uri"].startswith("data:image/svg+xml;base64,"))
        self.assertRegex(ctx["issued_time"], r"^\d{2}:\d{2}$")
        self.assertEqual(ctx["clues"], "")

    def test_rows_carry_generic_first_label(self):
        visit = self._visit("V-R13")
        self._consultation(visit)
        self._prescription(visit, [self.med], folio="RX-2026-13")
        row = self._build(visit).context["sheets"][0]["items"][0]
        self.assertEqual(row["label"]["primary"], "Paracetamol")

    def test_visit_not_found_404(self):
        with self.assertRaises(PrintError) as ctx:
            build_receta_context(999999, self.doctor)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_without_prescription_404(self):
        visit = self._visit("V-R2")
        self._consultation(visit)
        with self.assertRaises(PrintError) as ctx:
            self._build(visit)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("PRESCRIPTION_NOT_FOUND", 404))

    def test_open_consultation_409(self):
        visit = self._visit("V-R3", status="en_consulta")
        self._consultation(visit)
        self._prescription(visit, [self.med], folio="RX-2026-3")
        with self.assertRaises(PrintError) as ctx:
            self._build(visit)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("DOCUMENT_NOT_PRINTABLE", 409))

    def test_cancelled_note_409(self):
        visit = self._visit("V-R4", status="cancelada")
        self._consultation(visit)
        self._prescription(visit, [self.med], folio="RX-2026-4")
        with self.assertRaises(PrintError) as ctx:
            self._build(visit)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_pending_or_rejected_authorization_409(self):
        for i, status in enumerate(["pendiente", "rechazada"]):
            visit = self._visit(f"V-R5{i}")
            self._consultation(visit)
            rx = self._prescription(visit, [self.med], folio=f"RX-2026-5{i}")
            PrescriptionAuthorization.objects.create(prescription=rx, visit=visit, status=status)
            with self.subTest(status=status), self.assertRaises(PrintError) as ctx:
                self._build(visit)
            self.assertEqual(ctx.exception.status_code, 409)

    def test_authorized_prints(self):
        visit = self._visit("V-R6")
        self._consultation(visit)
        rx = self._prescription(visit, [self.med], folio="RX-2026-6")
        PrescriptionAuthorization.objects.create(prescription=rx, visit=visit, status="autorizada")
        self.assertEqual(self._build(visit).folio, "RX-2026-6")

    def test_no_active_items_409(self):
        visit = self._visit("V-R7")
        self._consultation(visit)
        rx = self._prescription(visit, [self.med], folio="RX-2026-7")
        rx.structured_items.update(status="cancelado")
        with self.assertRaises(PrintError) as ctx:
            self._build(visit)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_template_renders_sheets(self):
        visit = self._visit("V-R8")
        self._consultation(visit)
        self._prescription(visit, [self.med_ctrl], folio="RX-2026-8")
        pctx = self._build(visit)
        html = render_to_string(REGISTRY["receta"].template, dict(pctx.context, watermarks=[], copy_number=1))
        for text in ("RX-2026-8", "ORIGINAL", "COPIA", "CONTROLADO", "Clonazepam 2mg", "size: A5 landscape"):
            self.assertIn(text, html)

    def _render(self, meds, folio):
        visit = self._visit(f"V-{folio}")
        self._consultation(visit)
        self._prescription(visit, meds, folio=folio)
        pctx = self._build(visit)
        return render_to_string(REGISTRY["receta"].template, dict(pctx.context, watermarks=[], copy_number=1))

    def _render_sheets(self, meds, folio):
        # Una hoja por <div class="sheet">; el primer trozo es el <head>.
        return self._render(meds, folio).split('<div class="sheet">')[1:]

    def test_copy_sheet_has_stamp_and_original_does_not(self):
        original, copia = self._render_sheets([self.med], "RX-2026-10")
        self.assertIn('class="stamp"', copia)
        self.assertNotIn('class="stamp"', original)

    def test_controlled_sheet_omits_general_indications(self):
        original, _copia, controlado = self._render_sheets([self.med_ctrl], "RX-2026-11")
        self.assertIn("Tomar liquidos", original)
        self.assertNotIn("Tomar liquidos", controlado)

    def test_background_uses_local_asset(self):
        self.assertIn('url("fondos/receta-fondo-a5.jpg")', self._render([self.med], "RX-2026-12"))

    def test_a5_background_exists_and_has_a5_proportion(self):
        from pathlib import Path

        from PIL import Image

        from apps.impresion import engine

        path = Path(engine.__file__).resolve().parent / "static/impresion/fondos/receta-fondo-a5.jpg"
        with Image.open(path) as image:
            width, height = image.size
        # A5 horizontal: 210 x 148 mm.
        self.assertAlmostEqual(width / height, 210 / 148, places=2)


class NotaBuilderTests(_Base):
    def _build(self, visit, permissions=None):
        with mock.patch(HEADER, return_value=_header()), mock.patch(CLASSIFY, side_effect=_vih_only):
            return build_nota_context(visit.id_visit, self.doctor, permissions=permissions or [], roles=[])

    def test_closed_note_builds_and_omits_empty_sections(self):
        visit = self._visit("V-N1")
        self._consultation(visit)
        pctx = self._build(visit)
        labels = [s["label"] for s in pctx.context["sections"]]
        self.assertEqual(labels, ["Subjetivo", "Nota final"])
        self.assertFalse(pctx.is_cancelled)
        self.assertEqual(pctx.filename, "nota_V-N1.pdf")
        self.assertEqual(pctx.context["diagnoses"][0]["code"], "A090")

    def test_without_consultation_409(self):
        visit = self._visit("V-N2", status="en_consulta")
        with self.assertRaises(PrintError) as ctx:
            self._build(visit)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_open_note_409(self):
        visit = self._visit("V-N3", status="en_consulta")
        self._consultation(visit)
        with self.assertRaises(PrintError) as ctx:
            self._build(visit)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("DOCUMENT_NOT_PRINTABLE", 409))

    def test_cancelled_note_prints_flagged(self):
        visit = self._visit("V-N4", status="cancelada")
        self._consultation(visit)
        pctx = self._build(visit)
        self.assertTrue(pctx.is_cancelled)

    def test_sensitive_diagnosis_redacted_without_permission(self):
        visit = self._visit("V-N5")
        consultation = self._consultation(visit)
        VisitDiagnosis.objects.create(consultation=consultation, cie=self.cie_vih, notes="dx sensible")
        rows = self._build(visit).context["diagnoses"]
        self.assertEqual(rows[1]["code"], "")
        self.assertNotIn("VIH", rows[1]["description"])
        self.assertNotEqual(rows[1]["notes"], "dx sensible")

    def test_sensitive_diagnosis_visible_with_permission(self):
        visit = self._visit("V-N6")
        consultation = self._consultation(visit)
        VisitDiagnosis.objects.create(consultation=consultation, cie=self.cie_vih, notes="dx sensible")
        rows = self._build(visit, permissions=["clinico:diagnosticos_vih:read"]).context["diagnoses"]
        self.assertEqual(rows[1]["code"], "B24")

    def test_template_renders_key_fields(self):
        visit = self._visit("V-N7")
        self._consultation(visit)
        pctx = self._build(visit)
        html = render_to_string(REGISTRY["nota"].template, dict(pctx.context, watermarks=[], copy_number=1))
        for text in ("V-N7", "Juan Perez Lopez", "Dolor abdominal", "A090", "8.5in 5.5in"):
            self.assertIn(text, html)


class PrintUseCaseIntegrationTests(_Base):
    """Recorre el caso de uso real (engine mockeado): log, marca de agua, permisos."""

    def _print(self, documento, visit, permissions):
        request = RequestFactory().get("/")
        with mock.patch(HEADER, return_value=_header()), mock.patch(RENDER, return_value=b"%PDF-1.7") as render:
            result = uc.print_document(
                documento=documento, resource_id=visit.id_visit, user=self.doctor,
                permissions=permissions, request=request,
            )
        return result, render

    def test_receta_requires_print_permission(self):
        visit = self._visit("V-I1")
        self._consultation(visit)
        self._prescription(visit, [self.med], folio="RX-2026-I1")
        with self.assertRaises(PrintError) as ctx:
            self._print("receta", visit, ["clinico:consultas:read"])
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertFalse(PrintLog.objects.filter(documento="receta").exists())
        result, _ = self._print("receta", visit, ["clinico:recetas:imprimir"])
        self.assertEqual(result.tipo, PrintLog.Tipo.ORIGINAL)
        self.assertTrue(PrintLog.objects.filter(documento="receta", folio="RX-2026-I1").exists())

    def test_cancelled_note_gets_cancelada_watermark(self):
        visit = self._visit("V-I2", status="cancelada")
        self._consultation(visit)
        _, render = self._print("nota", visit, ["clinico:consultas:read"])
        marks = [w.label for w in render.call_args.args[1]["watermarks"]]
        self.assertIn("CANCELADA", marks)
