from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.authentication.services.errors import AuthServiceError
from apps.impresion.errors import PrintError
from apps.impresion.uses_case.print_document_usecase import PrintResult
from apps.impresion import views

UC = "apps.impresion.views.print_document"


class PrintApiTests(SimpleTestCase):
    def _get(self, documento="ficha", rid=5):
        request = APIRequestFactory().get(f"/api/v1/impresion/{documento}/{rid}")
        return views.PrintDocumentView.as_view()(request, documento=documento, resource_id=rid)

    def _auth_ok(self):
        user = mock.Mock()
        return (
            mock.patch("apps.impresion.views.authenticate_request", return_value=user),
            mock.patch("apps.impresion.views.UserRepository.build_auth_user", return_value={"permissions": ["p"]}),
        )

    def test_401_without_token(self):
        exc = AuthServiceError("UNAUTHENTICATED", "no", 401)
        with mock.patch("apps.impresion.views.authenticate_request", side_effect=exc):
            self.assertEqual(self._get().status_code, 401)

    def test_success_headers(self):
        a, b = self._auth_ok()
        result = PrintResult(pdf=b"%PDF-1", filename="ficha_F.pdf", copy_number=2, tipo="REIMPRESION", log_id=9)
        with a, b, mock.patch(UC, return_value=result) as uc:
            response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'inline; filename="ficha_F.pdf"')
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            (response["X-Print-Copy"], response["X-Print-Type"], response["X-Print-Log-Id"]),
            ("2", "REIMPRESION", "9"),
        )
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(uc.call_args.kwargs["permissions"], ["p"])

    def test_error_statuses_mapped(self):
        a, b = self._auth_ok()
        for code, status in (
            ("ROLE_NOT_ALLOWED", 403),
            ("VISIT_NOT_FOUND", 404),
            ("DOCUMENT_NOT_PRINTABLE", 409),
            ("PRINT_AUDIT_ERROR", 500),
            ("PRINT_BUSY", 503),
        ):
            with a, b, mock.patch(UC, side_effect=PrintError(code, "m", status)):
                response = self._get()
            self.assertEqual(response.status_code, status, code)
            self.assertEqual(response.data["code"], code)
            a, b = self._auth_ok()

    def test_busy_has_retry_after(self):
        a, b = self._auth_ok()
        with a, b, mock.patch(UC, side_effect=PrintError("PRINT_BUSY", "m", 503)):
            self.assertIn("Retry-After", self._get())

    def test_unexpected_error_is_500_generic(self):
        a, b = self._auth_ok()
        with a, b, mock.patch(UC, side_effect=RuntimeError("secret")):
            response = self._get()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", str(response.data))

    def test_url_resolves(self):
        from django.urls import resolve

        self.assertIs(
            resolve("/api/v1/impresion/ficha/3").func.view_class, views.PrintDocumentView
        )
