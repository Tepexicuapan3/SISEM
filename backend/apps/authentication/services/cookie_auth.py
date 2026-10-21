"""
Backend de autenticación DRF que lee el JWT desde la cookie HttpOnly.

Por qué existe:
  El proyecto guarda el access token en 'access_token_cookie' (HttpOnly).
  El JWTAuthentication por defecto de simplejwt busca en el header Authorization,
  no en cookies. Este backend adapta la lógica existente de authenticate_request
  para que los ModelViewSet puedan usarla sin duplicar código.
"""

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from .errors import AuthServiceError
from .session_service import authenticate_request


class CookieJWTAuthentication(BaseAuthentication):
    """Lee el access token desde la cookie y valida con la lógica existente."""

    def authenticate(self, request):
        try:
            user = authenticate_request(request)
            return (user, None)
        except AuthServiceError as exc:
            if exc.status_code == 401:
                raise AuthenticationFailed(exc.message) from exc
            if exc.code == "ONBOARDING_REQUIRED":
                # No degradar a "sin credenciales": responder 403 explicito.
                raise PermissionDenied(
                    {"code": exc.code, "message": exc.message}
                ) from exc
            return None

    def authenticate_header(self, request):
        return "Cookie"
