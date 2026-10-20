from unittest import mock

from django.test import RequestFactory, TestCase, override_settings

from apps.administracion.models import BitacoraAcceso
from apps.authentication.models import SyUsuario
from apps.consulta_medica.services.record_access_audit_service import RecordSection
from apps.impresion.errors import PrintError
from apps.impresion.models import PrintCounter, PrintLog
from apps.impresion.registry import REGISTRY, DocumentSpec, PrintContext
from apps.impresion.uses_case import print_document_usecase as uc

PERMS = ["clinico:consultas:read"]
RENDER = "apps.impresion.uses_case.print_document_usecase.engine.render_pdf"
BUILDER = "apps.impresion.tests.test_print_document_usecase.fake_builder"


def fake_builder(resource_id, actor, *, permissions=None, roles=None):
    if resource_id == 404:
        raise PrintError("VISIT_NOT_FOUND", "no", 404)
    return PrintContext(
        context={"x": 1},
        no_exp="E1",
        pk_num=0,
        folio="F-1",
        filename="fake_F-1.pdf",
        center_id=7,
    )


def _spec(**kw):
    base = dict(
        key="fake",
        template="t.html",
        builder=BUILDER,
        capability="documentos.nota.imprimir",
        section=RecordSection.NOTA,
    )
    base.update(kw)
    return DocumentSpec(**base)


class PrintDocumentUseCaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = SyUsuario.objects.create(usuario="u_print", clave_hash="x")

    def setUp(self):
        patcher = mock.patch.dict(REGISTRY, {"fake": _spec(), "fake_noreprint": _spec(key="fake_noreprint", watermark_on_reprint=False)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.request = RequestFactory().get("/api/v1/impresion/fake/1")

    def _print(self, documento="fake", resource_id=1, permissions=PERMS, user=None):
        return uc.print_document(
            documento=documento,
            resource_id=resource_id,
            user=user or self.user,
            permissions=permissions,
            request=self.request,
        )

    def test_first_print_original_then_reimpresion(self):
        with mock.patch(RENDER, return_value=b"%PDF-1") as render:
            first = self._print()
            second = self._print()
        self.assertEqual((first.copy_number, first.tipo), (1, "ORIGINAL"))
        self.assertEqual((second.copy_number, second.tipo), (2, "REIMPRESION"))
        self.assertEqual(PrintLog.objects.count(), 2)
        self.assertEqual(
            BitacoraAcceso.objects.filter(accion=BitacoraAcceso.Accion.IMPRIMIR).count(), 2
        )
        row = PrintLog.objects.get(copy_number=2)
        self.assertEqual((row.documento, row.resource_id, row.folio, row.engine), ("fake", 1, "F-1", "weasy"))
        self.assertEqual(len(row.sha256), 64)
        labels1 = [w.label for w in render.call_args_list[0].args[1]["watermarks"]]
        labels2 = [w.label for w in render.call_args_list[1].args[1]["watermarks"]]
        self.assertEqual(labels1, [])
        self.assertEqual(labels2, ["REIMPRESIÓN"])
        self.assertEqual(render.call_args_list[1].args[1]["copy_number"], 2)

    def test_watermark_off_still_logs_reprint(self):
        with mock.patch(RENDER, return_value=b"%PDF-1") as render:
            self._print("fake_noreprint")
            self._print("fake_noreprint")
        self.assertEqual(render.call_args_list[1].args[1]["watermarks"], [])
        self.assertEqual(PrintLog.objects.filter(tipo="REIMPRESION").count(), 1)

    def test_unknown_document_404(self):
        with self.assertRaises(PrintError) as ctx:
            self._print("nope")
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("DOCUMENT_TYPE_NOT_FOUND", 404))

    def test_without_capability_403_no_log(self):
        with mock.patch(RENDER, return_value=b"%PDF-1"):
            with self.assertRaises(PrintError) as ctx:
                self._print(permissions=["recepcion:citas:read"])
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(PrintLog.objects.count(), 0)

    def test_builder_404_no_log(self):
        with self.assertRaises(PrintError) as ctx:
            self._print(resource_id=404)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(PrintLog.objects.count(), 0)

    def test_other_center_403(self):
        with mock.patch.object(uc, "_assignment_center_id", return_value=99):
            with self.assertRaises(PrintError) as ctx:
                self._print()
            self.assertEqual(ctx.exception.status_code, 403)
            with mock.patch(RENDER, return_value=b"%PDF-1"):
                self.assertEqual(self._print(permissions=["*"]).copy_number, 1)
        self.assertEqual(PrintLog.objects.count(), 1)

    def test_same_or_unassigned_center_allowed(self):
        with mock.patch(RENDER, return_value=b"%PDF-1"):
            with mock.patch.object(uc, "_assignment_center_id", return_value=7):
                self._print()
            with mock.patch.object(uc, "_assignment_center_id", return_value=None):
                self._print()
        self.assertEqual(PrintLog.objects.count(), 2)

    def test_render_failure_no_rows_counter_rolled_back(self):
        err = PrintError("PRINT_RENDER_ERROR", "x", 500)
        with mock.patch(RENDER, side_effect=err):
            with self.assertRaises(PrintError):
                self._print()
        self.assertEqual(PrintLog.objects.count(), 0)
        self.assertEqual(BitacoraAcceso.objects.count(), 0)
        self.assertEqual(PrintCounter.objects.count(), 0)

    def test_audit_failure_rolls_back_everything(self):
        with mock.patch(RENDER, return_value=b"%PDF-1"):
            with mock.patch.object(uc, "log_print", side_effect=RuntimeError("db")):
                with self.assertRaises(PrintError) as ctx:
                    self._print()
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("PRINT_AUDIT_ERROR", 500))
        self.assertEqual(PrintLog.objects.count(), 0)
        self.assertEqual(BitacoraAcceso.objects.count(), 0)
        self.assertEqual(PrintCounter.objects.count(), 0)

    def test_printlog_failure_rolls_back_bitacora_not_written(self):
        with mock.patch(RENDER, return_value=b"%PDF-1"):
            with mock.patch.object(uc.PrintLogRepository, "create_log", side_effect=RuntimeError("db")):
                with self.assertRaises(PrintError) as ctx:
                    self._print()
        self.assertEqual(ctx.exception.code, "PRINT_AUDIT_ERROR")
        self.assertEqual(BitacoraAcceso.objects.count(), 0)

    def test_log_event_runs_post_commit_and_failure_is_swallowed(self):
        with mock.patch(RENDER, return_value=b"%PDF-1"):
            with mock.patch.object(uc, "log_event", side_effect=RuntimeError("boom")) as ev:
                with self.assertLogs(uc.logger, level="ERROR"):
                    with self.captureOnCommitCallbacks(execute=True):
                        result = self._print()
                ev.assert_called_once()
        self.assertEqual(result.copy_number, 1)
        self.assertEqual(PrintLog.objects.count(), 1)

    def test_clinical_rows_untouched(self):
        # Solo PrintLog/PrintCounter/BitacoraAcceso cambian.
        from apps.recepcion.models import Visit

        before = Visit.objects.count()
        with mock.patch(RENDER, return_value=b"%PDF-1"):
            self._print()
        self.assertEqual(Visit.objects.count(), before)

    @override_settings(PRINT_MAX_CONCURRENCY=1, PRINT_QUEUE_TIMEOUT_S=0.05)
    def test_busy_returns_503_without_log(self):
        sem = uc._get_semaphore()
        self.assertTrue(sem.acquire(timeout=1))
        try:
            with mock.patch(RENDER, return_value=b"%PDF-1"):
                with self.assertRaises(PrintError) as ctx:
                    self._print()
        finally:
            sem.release()
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("PRINT_BUSY", 503))
        self.assertEqual(PrintLog.objects.count(), 0)

    @override_settings(PRINT_MAX_CONCURRENCY=1, PRINT_QUEUE_TIMEOUT_S=1)
    def test_semaphore_released_after_failure(self):
        with mock.patch(RENDER, side_effect=PrintError("PRINT_RENDER_ERROR", "x", 500)):
            with self.assertRaises(PrintError):
                self._print()
        sem = uc._get_semaphore()
        self.assertTrue(sem.acquire(timeout=0.5))
        sem.release()

    @override_settings(FICHA_ENGINE="docx")
    def test_docx_engine_flag_uses_legacy_renderer_and_logs(self):
        REGISTRY["fake"] = _spec(
            key="ficha",
            legacy_renderer="apps.impresion.tests.test_print_document_usecase.fake_docx",
        )
        with mock.patch(RENDER) as render:
            result = self._print()
        render.assert_not_called()
        self.assertEqual(result.pdf, b"%PDF-docx")
        self.assertEqual(PrintLog.objects.get().engine, "docx")


def fake_docx(print_context, actor):
    return b"%PDF-docx"
