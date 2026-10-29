from unittest import mock

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Medicamentos
from apps.consulta_medica.impresion.nota import build_nota_context
from apps.consulta_medica.impresion.receta import build_receta_context, build_sheets
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


class RecetaSheetsTests(TestCase):
    def test_no_controlled_two_sheets(self):
        sheets = build_sheets([{"is_controlled": False}])
        self.assertEqual([s["label"] for s in sheets], ["ORIGINAL", "COPIA"])

    def test_controlled_adds_sheet_with_only_controlled_items(self):
        rows = [{"is_controlled": False, "name": "a"}, {"is_controlled": True, "name": "b"}]
        sheets = build_sheets(rows)
        self.assertEqual([s["label"] for s in sheets], ["ORIGINAL", "COPIA", "CONTROLADO"])
        self.assertEqual([r["name"] for r in sheets[2]["items"]], ["b"])


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
        for text in ("RX-2026-8", "ORIGINAL", "COPIA", "CONTROLADO", "Clonazepam 2mg", "720pt 490pt"):
            self.assertIn(text, html)


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
