"""
apps/impresion/views.py
===========================
GET /api/v1/impresion/<documento>/<int:resource_id>

Endpoint generico de impresion. ``handle_print`` tambien lo usan los alias
de compatibilidad (p. ej. ``/visits/<id>/ficha``).
"""

import logging

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.response_service import error_response, get_request_id
from apps.authentication.services.session_service import authenticate_request
from apps.impresion.errors import PrintError
from apps.impresion.uses_case.print_document_usecase import print_document

logger = logging.getLogger(__name__)


def handle_print(request, documento, resource_id):
    """Autentica, ejecuta el caso de uso y arma la respuesta HTTP."""
    request_id = get_request_id(request)
    try:
        user = authenticate_request(request)
    except AuthServiceError as exc:
        return error_response(
            exc.code, exc.message, exc.status_code,
            details=exc.details, request_id=request_id,
        )

    permissions = UserRepository.build_auth_user(user).get("permissions", [])
    try:
        result = print_document(
            documento=documento,
            resource_id=resource_id,
            user=user,
            permissions=permissions,
            request=request,
        )
    except PrintError as exc:
        response = error_response(
            exc.code, exc.message, exc.status_code,
            details=exc.details, request_id=request_id,
        )
        if exc.status_code == 503:
            response["Retry-After"] = "5"
        return response
    except Exception:
        logger.exception("Error inesperado imprimiendo %s/%s", documento, resource_id)
        return error_response(
            "PRINT_RENDER_ERROR", "No se pudo generar el documento", 500,
            request_id=request_id,
        )

    response = HttpResponse(result.pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{result.filename}"'
    response["Cache-Control"] = "no-store"
    response["X-Print-Copy"] = str(result.copy_number)
    response["X-Print-Type"] = result.tipo
    response["X-Print-Log-Id"] = str(result.log_id)
    return response


@method_decorator(csrf_exempt, name="dispatch")
class PrintDocumentView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, documento, resource_id):
        return handle_print(request, documento, resource_id)
