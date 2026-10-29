import importlib.util
import unittest
from unittest import mock

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings

from apps.authentication.models import SyUsuario
from apps.impresion.errors import PrintError
from apps.impresion.models import PrintLog
from apps.impresion.registry import REGISTRY
from apps.impresion.uses_case import print_document_usecase as uc
from apps.recepcion.impresion.ficha import build_ficha_context
from apps.recepcion.models import Visit
from apps.recepcion.views.ficha_views import FichaVisitView
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave

RENDER = "apps.impresion.uses_case.print_document_usecase.engine.render_pdf"
HEADER = "apps.recepcion.impresion.ficha.get_patient_header"
PERMS = ["clinico:consultas:read"]


def _header(source="cns_paciente"):
    return {
        "no_exp": "E1", "pk_num": 0, "paternal_surname": "Perez", "maternal_surname": "Lopez",
        "first_name": "Juan", "full_name": "Juan Perez Lopez", "age": "40",
        "birth_date": "01/01/1985", "sex": "M", "source": source,
    }


class FichaBuilderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = SyUsuario.objects.create(usuario="u_ficha", clave_hash="x")
        cls.visit = Visit.objects.create(folio="FOL-001", patient=_paciente_de_llave("E1", 0), arrival_type="walk_in", service_type="medicina_general", nombre_paciente="Visit Name")

    def test_registry_ficha_spec(self):
        spec = REGISTRY["ficha"]
        self.assertFalse(spec.watermark_on_reprint)
        self.assertEqual(spec.capability, "documentos.ficha.imprimir")

    def test_builder_context(self):
        with mock.patch(HEADER, return_value=_header()):
            pctx = build_ficha_context(self.visit.id_visit, self.user)
        self.assertEqual(pctx.folio, "FOL-001")
        self.assertEqual(pctx.filename, "ficha_FOL-001.pdf")
        self.assertEqual(pctx.no_exp, "E1")
        self.assertFalse(pctx.is_cancelled)
        self.assertEqual(pctx.context["paciente_nombre_completo"], "Juan Perez Lopez")
        self.assertEqual(pctx.context["a_paterno"], "Perez")
        self.assertEqual(pctx.context["folio_ficha"], "FOL-001")
        self.assertTrue(pctx.context["barcode_uri"].startswith("data:image/svg+xml"))

    def test_builder_does_not_query_sermed_directly(self):
        with mock.patch(HEADER, return_value=_header()), mock.patch(
            "apps.recepcion.services.ficha_service._get_nombre_components"
        ) as legacy:
            build_ficha_context(self.visit.id_visit, self.user)
        legacy.assert_not_called()

    def test_visit_not_found_404(self):
        with self.assertRaises(PrintError) as ctx:
            build_ficha_context(999999, self.user)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("VISIT_NOT_FOUND", 404))

    def test_unresolvable_patient_409(self):
        with mock.patch(HEADER, return_value=dict(_header(), source=None, full_name="")):
            with self.assertRaises(PrintError) as ctx:
                build_ficha_context(self.visit.id_visit, self.user)
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("DOCUMENT_NOT_PRINTABLE", 409))

    def test_template_renders_key_fields(self):
        with mock.patch(HEADER, return_value=_header()):
            pctx = build_ficha_context(self.visit.id_visit, self.user)
        html = render_to_string(REGISTRY["ficha"].template, dict(pctx.context, watermarks=[], copy_number=1))
        self.assertIn("FOL-001", html)
        self.assertIn("Juan Perez Lopez", html)
        self.assertIn("A5 landscape", html)


class FichaReprintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = SyUsuario.objects.create(usuario="u_ficha2", clave_hash="x")
        cls.visit = Visit.objects.create(folio="FOL-002", patient=_paciente_de_llave("E1", 0), arrival_type="walk_in", service_type="medicina_general", nombre_paciente="Visit Name")

    def _print(self):
        return uc.print_document(
            documento="ficha", resource_id=self.visit.id_visit, user=self.user,
            permissions=PERMS, request=RequestFactory().get("/x"),
        )

    def test_reprint_logged_without_watermark(self):
        with mock.patch(HEADER, return_value=_header()), mock.patch(RENDER, return_value=b"%PDF-1") as render:
            self._print()
            second = self._print()
        self.assertEqual(second.tipo, "REIMPRESION")
        self.assertEqual(render.call_args_list[1].args[1]["watermarks"], [])
        self.assertEqual(PrintLog.objects.filter(documento="ficha", tipo="REIMPRESION").count(), 1)

    @override_settings(FICHA_ENGINE="docx")
    def test_docx_flag_goes_through_same_log(self):
        with mock.patch(HEADER, return_value=_header()), mock.patch(RENDER) as render, mock.patch(
            "apps.recepcion.impresion.ficha.ficha_service.generate_ficha_pdf", return_value=b"%PDF-docx"
        ) as gen:
            result = self._print()
        render.assert_not_called()
        gen.assert_called_once()
        self.assertEqual(result.pdf, b"%PDF-docx")
        self.assertEqual(PrintLog.objects.get().engine, "docx")


class FichaAliasViewTests(TestCase):
    def test_alias_delegates_to_generic_use_case(self):
        request = RequestFactory().get("/api/v1/visits/7/ficha")
        with mock.patch("apps.recepcion.views.ficha_views.handle_print", return_value="resp") as hp:
            response = FichaVisitView().get(request, 7)
        self.assertEqual(response, "resp")
        hp.assert_called_once_with(request, "ficha", 7)

    def test_alias_url_still_routed(self):
        from django.urls import resolve

        self.assertIs(resolve("/api/v1/visits/7/ficha").func.view_class, FichaVisitView)


@unittest.skipUnless(importlib.util.find_spec("weasyprint"), "weasyprint no disponible")
class FichaRealPdfTests(TestCase):
    def test_real_pdf(self):
        user = SyUsuario.objects.create(usuario="u_real", clave_hash="x")
        visit = Visit.objects.create(folio="FOL-REAL", patient=_paciente_de_llave("E1", 0), arrival_type="walk_in", service_type="medicina_general", nombre_paciente="X")
        try:
            with mock.patch(HEADER, return_value=_header()):
                result = uc.print_document(
                    documento="ficha", resource_id=visit.id_visit, user=user,
                    permissions=PERMS, request=RequestFactory().get("/x"),
                )
        except PrintError as exc:
            self.skipTest(f"WeasyPrint sin libs nativas: {exc.code}")
        self.assertTrue(result.pdf.startswith(b"%PDF"))
