from rest_framework.permissions import BasePermission

from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.session_service import authenticate_request
from apps.catalogos.permissions import MUTATING_METHODS, CatalogApiException


class SesionActiva(BasePermission):
    """Cada usuario consulta y marca SOLO sus propias notificaciones: basta la
    sesion (cookie) y el CSRF en mutaciones; no hace falta un permiso atomico.
    Mismo orden que HasCatalogPermission: CSRF primero, despues sesion."""

    def has_permission(self, request, _view) -> bool:
        request_id = request.headers.get("X-Request-ID")
        if request.method in MUTATING_METHODS and not validate_csrf(request):
            raise CatalogApiException(
                code="CSRF_INVALID", message="Token CSRF inválido o ausente", http_status=403, request_id=request_id,
            )
        try:
            request.user = authenticate_request(request)
        except AuthServiceError as exc:
            raise CatalogApiException(
                code=exc.code, message=exc.message, http_status=exc.status_code,
                request_id=request_id, details=exc.details,
            )
        return True
