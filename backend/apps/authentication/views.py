import time

from apps.administracion.services.rbac_resolver import RBACResolver
from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.serializers import (
    ChangePasswordSerializer,
    CompleteOnboardingSerializer,
    LoginSerializer,
    RequestResetCodeSerializer,
    ResetPasswordSerializer,
    VerifyResetCodeSerializer,
)
from apps.authentication.services.audit_service import (
    log_event,
    mask_email,
    mask_username,
)
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import (
    AuthServiceError,
    PolicyStoreUnavailableError,
)
from apps.authentication.services.observability_service import (
    build_observability_snapshot,
    observe_latency_ms,
    record_login_result,
    record_policy_deny,
)
from apps.authentication.services.response_service import (
    error_response,
    get_client_ip,
    get_request_id,
)
from apps.authentication.services.session_registry import close_session
from apps.authentication.services.session_revocation import rotate_user_session
from apps.authentication.services.session_service import authenticate_request
from apps.authentication.services.token_service import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    clear_reset_cookie,
    generate_csrf_token,
    set_auth_cookies,
    set_csrf_cookie,
    set_reset_cookie,
)
from apps.authentication.uses_case.list_sessions_usecase import list_sessions
from apps.authentication.uses_case.login_usecase import login_user
from apps.authentication.uses_case.me_usecase import (
    build_capabilities_response,
    build_me_response,
)
from apps.authentication.uses_case.change_password_usecase import change_password
from apps.authentication.uses_case.onboarding_usecase import complete_onboarding
from apps.authentication.uses_case.refresh_usecase import refresh_tokens
from apps.authentication.uses_case.request_reset_code_usecase import request_reset_code
from apps.authentication.uses_case.reset_password_usecase import reset_password
from apps.authentication.uses_case.verify_reset_code_usecase import verify_reset_code
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


def _csrf_or_error(request):
    # Valida CSRF usando cookie y header.
    if validate_csrf(request):
        return None
    return error_response(
        "PERMISSION_DENIED",
        "No tienes permiso para esta acción",
        status.HTTP_403_FORBIDDEN,
        request_id=get_request_id(request),
    )


def _policy_meta_from_error(exc):
    if not getattr(exc, "details", None):
        return {}
    return exc.details.get("policy", {}) or {}


def _log_policy_deny_if_needed(request, exc, base_meta):
    if exc.code not in {"RATE_LIMIT_EXCEEDED", "ACCOUNT_LOCKED", "SERVICE_UNAVAILABLE"}:
        return

    record_policy_deny(exc.code)

    log_event(
        request,
        "POLICY_ENFORCEMENT_DENY",
        "FAIL",
        error_code=exc.code,
        meta={**base_meta, **_policy_meta_from_error(exc)},
    )


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        start = time.perf_counter()
        try:
            serializer = LoginSerializer(data=request.data)
            if not serializer.is_valid():
                record_login_result("FAIL", error_code="INVALID_CREDENTIALS")
                log_event(
                    request,
                    "LOGIN_FAILED",
                    "FAIL",
                    error_code="INVALID_CREDENTIALS",
                    meta={
                        "endpoint": "/auth/login",
                        "username": mask_username(request.data.get("username")),
                    },
                )
                return error_response(
                    "INVALID_CREDENTIALS",
                    "Usuario o contraseña incorrectos",
                    status.HTTP_401_UNAUTHORIZED,
                    details=serializer.errors,
                    request_id=get_request_id(request),
                )

            try:
                result = login_user(
                    serializer.validated_data["username"],
                    serializer.validated_data["password"],
                    get_client_ip(request),
                    request.META.get("HTTP_USER_AGENT"),
                )
            except AuthServiceError as exc:
                record_login_result("FAIL", error_code=exc.code)
                user = UserRepository.get_by_username(
                    serializer.validated_data.get("username")
                )
                base_meta = {
                    "endpoint": "/auth/login",
                    "username": mask_username(serializer.validated_data.get("username")),
                }
                _log_policy_deny_if_needed(request, exc, base_meta)
                log_event(
                    request,
                    "LOGIN_FAILED",
                    "FAIL",
                    actor_user=user,
                    target_user=user,
                    error_code=exc.code,
                    meta={**base_meta, **_policy_meta_from_error(exc)},
                )
                return error_response(
                    exc.code,
                    exc.message,
                    exc.status_code,
                    details=exc.details,
                    request_id=get_request_id(request),
                )
            except Exception:
                record_login_result("FAIL", error_code="INTERNAL_SERVER_ERROR")
                log_event(
                    request,
                    "LOGIN_FAILED",
                    "FAIL",
                    error_code="INTERNAL_SERVER_ERROR",
                    meta={"endpoint": "/auth/login"},
                )
                return error_response(
                    "INTERNAL_SERVER_ERROR",
                    "Error del servidor, intenta nuevamente",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    request_id=get_request_id(request),
                )

            response_body = {
                "user": result["user"],
                "requiresOnboarding": result["requires_onboarding"],
            }
            response = Response(response_body, status=status.HTTP_200_OK)
            # Genera cookies tras login exitoso.
            csrf_token = generate_csrf_token()
            set_auth_cookies(
                response,
                result["access_token"],
                result["refresh_token"],
                csrf_token,
            )
            log_event(
                request,
                "LOGIN_SUCCESS",
                "SUCCESS",
                actor_user=UserRepository.get_by_username(
                    serializer.validated_data["username"]
                ),
                target_user=UserRepository.get_by_username(
                    serializer.validated_data["username"]
                ),
                meta={
                    "endpoint": "/auth/login",
                    "username": mask_username(serializer.validated_data.get("username")),
                },
            )
            record_login_result("SUCCESS")
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            observe_latency_ms("/auth/login", elapsed_ms)


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            user = authenticate_request(request)
        except AuthServiceError as exc:
            log_event(
                request,
                "LOGOUT",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/logout"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            log_event(
                request,
                "LOGOUT",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="PERMISSION_DENIED",
                meta={"endpoint": "/auth/logout"},
            )
            return csrf_error

        response = Response(
            {"success": True},
            status=status.HTTP_200_OK,
        )
        # Limpia cookies para cerrar la sesion (esto SIEMPRE debe pasar).
        clear_auth_cookies(response)
        try:
            # Libera la sesion activa (Redis) y cierra el historial (Postgres).
            close_session(user, getattr(request, "session_id", None))
        except PolicyStoreUnavailableError:
            # Redis caido: el logout del lado del cliente ya es efectivo
            # (cookies limpias). La sesion se liberara sola cuando venza el TTL.
            pass
        log_event(
            request,
            "LOGOUT",
            "SUCCESS",
            actor_user=user,
            target_user=user,
            meta={"endpoint": "/auth/logout"},
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class MeView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            user = authenticate_request(request)
        except AuthServiceError as exc:
            log_event(
                request,
                "SESSION_VALIDATE",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/me"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )

        log_event(
            request,
            "SESSION_VALIDATE",
            "SUCCESS",
            actor_user=user,
            target_user=user,
            meta={"endpoint": "/auth/me"},
        )
        return Response(build_me_response(user), status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class CapabilitiesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        start = time.perf_counter()
        try:
            try:
                user = authenticate_request(request)
            except AuthServiceError as exc:
                log_event(
                    request,
                    "CAPABILITIES_READ",
                    "FAIL",
                    error_code=exc.code,
                    meta={"endpoint": "/auth/capabilities"},
                )
                return error_response(
                    exc.code,
                    exc.message,
                    exc.status_code,
                    details=exc.details,
                    request_id=get_request_id(request),
                )

            try:
                capabilities_payload = build_capabilities_response(user)
            except Exception:
                log_event(
                    request,
                    "CAPABILITIES_READ",
                    "FAIL",
                    actor_user=user,
                    target_user=user,
                    error_code="INTERNAL_SERVER_ERROR",
                    meta={"endpoint": "/auth/capabilities"},
                )
                return error_response(
                    "INTERNAL_SERVER_ERROR",
                    "Error del servidor, intenta nuevamente",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    request_id=get_request_id(request),
                )

            log_event(
                request,
                "CAPABILITIES_READ",
                "SUCCESS",
                actor_user=user,
                target_user=user,
                meta={"endpoint": "/auth/capabilities"},
            )
            return Response(capabilities_payload, status=status.HTTP_200_OK)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            observe_latency_ms("/auth/capabilities", elapsed_ms)


@method_decorator(csrf_exempt, name="dispatch")
class AuthAccessObservabilityView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            user = authenticate_request(request)
        except AuthServiceError as exc:
            log_event(
                request,
                "AUTH_ACCESS_OBSERVABILITY_READ",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/ops/observability"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )

        permissions = RBACResolver.get_effective_permissions(user)
        has_observability_access = "*" in permissions or "admin:ops:observability:read" in permissions
        if not has_observability_access:
            log_event(
                request,
                "AUTH_ACCESS_OBSERVABILITY_READ",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="PERMISSION_DENIED",
                meta={"endpoint": "/auth/ops/observability"},
            )
            return error_response(
                "PERMISSION_DENIED",
                "No tienes permiso para esta acción",
                status.HTTP_403_FORBIDDEN,
                request_id=get_request_id(request),
            )

        snapshot = build_observability_snapshot()
        log_event(
            request,
            "AUTH_ACCESS_OBSERVABILITY_READ",
            "SUCCESS",
            actor_user=user,
            target_user=user,
            meta={"endpoint": "/auth/ops/observability"},
        )
        return Response(snapshot, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class UserSessionsView(APIView):
    # Vista admin: historial + conexiones activas (IP, inicio, fin, duracion).
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            user = authenticate_request(request)
        except AuthServiceError as exc:
            log_event(
                request,
                "SESSIONS_READ",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/ops/sessions"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )

        permissions = RBACResolver.get_effective_permissions(user)
        has_access = "*" in permissions or "admin:usuarios:sesiones:read" in permissions
        if not has_access:
            log_event(
                request,
                "SESSIONS_READ",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="PERMISSION_DENIED",
                meta={"endpoint": "/auth/ops/sessions"},
            )
            return error_response(
                "PERMISSION_DENIED",
                "No tienes permiso para esta acción",
                status.HTTP_403_FORBIDDEN,
                request_id=get_request_id(request),
            )

        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("pageSize", "20"))
        except (TypeError, ValueError):
            return error_response(
                "INVALID_FORMAT",
                "Parámetros de paginación inválidos",
                status.HTTP_400_BAD_REQUEST,
                request_id=get_request_id(request),
            )

        if page < 1 or page_size < 1 or page_size > 100:
            return error_response(
                "VALIDATION_ERROR",
                "Parámetros de paginación fuera de rango",
                status.HTTP_400_BAD_REQUEST,
                request_id=get_request_id(request),
            )

        solo_activas = request.query_params.get("soloActivas") == "true"
        payload = list_sessions(
            page,
            page_size,
            usuario=request.query_params.get("usuario"),
            solo_activas=solo_activas,
        )
        log_event(
            request,
            "SESSIONS_READ",
            "SUCCESS",
            actor_user=user,
            target_user=user,
            meta={"endpoint": "/auth/ops/sessions"},
        )
        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VerifyView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            authenticate_request(request)
        except AuthServiceError as exc:
            status_code = (
                status.HTTP_403_FORBIDDEN
                if exc.code == "PERMISSION_DENIED"
                else status.HTTP_401_UNAUTHORIZED
            )
            return Response({"valid": False}, status=status_code)

        return Response({"valid": True}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class RefreshView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh_token:
            log_event(
                request,
                "TOKEN_REFRESH",
                "FAIL",
                error_code="TOKEN_INVALID",
                meta={"endpoint": "/auth/refresh"},
            )
            return error_response(
                "TOKEN_INVALID",
                "Token inválido",
                status.HTTP_401_UNAUTHORIZED,
                request_id=get_request_id(request),
            )

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            log_event(
                request,
                "TOKEN_REFRESH",
                "FAIL",
                error_code="PERMISSION_DENIED",
                meta={"endpoint": "/auth/refresh"},
            )
            return csrf_error

        try:
            result = refresh_tokens(refresh_token)
        except AuthServiceError as exc:
            log_event(
                request,
                "TOKEN_REFRESH",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/refresh"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )
        except Exception:
            log_event(
                request,
                "TOKEN_REFRESH",
                "FAIL",
                error_code="INTERNAL_SERVER_ERROR",
                meta={"endpoint": "/auth/refresh"},
            )
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        response = Response({"success": True}, status=status.HTTP_200_OK)
        # Rota tokens al refrescar.
        csrf_token = generate_csrf_token()
        set_auth_cookies(
            response,
            result["access_token"],
            result["refresh_token"],
            csrf_token,
        )
        log_event(
            request,
            "TOKEN_REFRESH",
            "SUCCESS",
            meta={"endpoint": "/auth/refresh"},
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class CompleteOnboardingView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            user = authenticate_request(request)
        except AuthServiceError as exc:
            log_event(
                request,
                "ONBOARDING_FAILED",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/complete-onboarding"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            log_event(
                request,
                "ONBOARDING_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="PERMISSION_DENIED",
                meta={"endpoint": "/auth/complete-onboarding"},
            )
            return csrf_error

        serializer = CompleteOnboardingSerializer(data=request.data)
        if not serializer.is_valid():
            log_event(
                request,
                "ONBOARDING_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="VALIDATION_ERROR",
                meta={"endpoint": "/auth/complete-onboarding"},
            )
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        try:
            result = complete_onboarding(
                user,
                serializer.validated_data["newPassword"],
                serializer.validated_data["termsAccepted"],
                get_client_ip(request),
                getattr(request, "session_id", None),
            )
        except AuthServiceError as exc:
            log_event(
                request,
                "ONBOARDING_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code=exc.code,
                meta={"endpoint": "/auth/complete-onboarding"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )
        except Exception:
            log_event(
                request,
                "ONBOARDING_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="ONBOARDING_FAILED",
                meta={"endpoint": "/auth/complete-onboarding"},
            )
            return error_response(
                "ONBOARDING_FAILED",
                "No se pudo completar el onboarding",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        response = Response(
            {
                "user": result["user"],
                "requiresOnboarding": bool(result["user"].get("requiresOnboarding")),
            },
            status=status.HTTP_200_OK,
        )
        # Re-emite tokens al completar onboarding.
        csrf_token = generate_csrf_token()
        set_auth_cookies(
            response,
            result["access_token"],
            result["refresh_token"],
            csrf_token,
        )
        log_event(
            request,
            "ONBOARDING_COMPLETED",
            "SUCCESS",
            actor_user=user,
            target_user=user,
            meta={"endpoint": "/auth/complete-onboarding"},
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class RequestResetCodeView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RequestResetCodeSerializer(data=request.data)
        if not serializer.is_valid():
            error_code = (
                "INVALID_EMAIL" if "email" in serializer.errors else "VALIDATION_ERROR"
            )
            message = (
                "Email inválido"
                if error_code == "INVALID_EMAIL"
                else "Hay errores en el formulario"
            )
            log_event(
                request,
                "RESET_CODE_REQUESTED",
                "FAIL",
                error_code=error_code,
                meta={
                    "endpoint": "/auth/request-reset-code",
                    "email": mask_email(request.data.get("email")),
                },
            )
            return error_response(
                error_code,
                message,
                status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        try:
            user = request_reset_code(
                serializer.validated_data["email"],
                get_client_ip(request),
            )
        except AuthServiceError as exc:
            base_meta = {
                "endpoint": "/auth/request-reset-code",
                "email": mask_email(serializer.validated_data.get("email")),
            }
            _log_policy_deny_if_needed(request, exc, base_meta)
            log_event(
                request,
                "RESET_CODE_REQUESTED",
                "FAIL",
                error_code=exc.code,
                meta={**base_meta, **_policy_meta_from_error(exc)},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )
        except Exception:
            log_event(
                request,
                "RESET_CODE_REQUESTED",
                "FAIL",
                error_code="INTERNAL_SERVER_ERROR",
                meta={"endpoint": "/auth/request-reset-code"},
            )
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        log_event(
            request,
            "RESET_CODE_REQUESTED",
            "SUCCESS",
            actor_user=user,
            target_user=user,
            meta={
                "endpoint": "/auth/request-reset-code",
                "email": mask_email(serializer.validated_data.get("email")),
            },
        )
        return Response({"success": True}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VerifyResetCodeView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = VerifyResetCodeSerializer(data=request.data)
        if not serializer.is_valid():
            error_code = (
                "INVALID_EMAIL" if "email" in serializer.errors else "INVALID_CODE"
            )
            message = (
                "Email inválido"
                if error_code == "INVALID_EMAIL"
                else "Código incorrecto"
            )
            log_event(
                request,
                "RESET_CODE_FAILED",
                "FAIL",
                error_code=error_code,
                meta={
                    "endpoint": "/auth/verify-reset-code",
                    "email": mask_email(request.data.get("email")),
                },
            )
            return error_response(
                error_code,
                message,
                status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        try:
            result = verify_reset_code(
                serializer.validated_data["email"],
                serializer.validated_data["code"],
                get_client_ip(request),
            )
        except AuthServiceError as exc:
            base_meta = {
                "endpoint": "/auth/verify-reset-code",
                "email": mask_email(serializer.validated_data.get("email")),
            }
            _log_policy_deny_if_needed(request, exc, base_meta)
            log_event(
                request,
                "RESET_CODE_FAILED",
                "FAIL",
                error_code=exc.code,
                meta={**base_meta, **_policy_meta_from_error(exc)},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )
        except Exception:
            log_event(
                request,
                "RESET_CODE_FAILED",
                "FAIL",
                error_code="INTERNAL_SERVER_ERROR",
                meta={"endpoint": "/auth/verify-reset-code"},
            )
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        response = Response({"valid": True}, status=status.HTTP_200_OK)
        # Token temporal para el reset.
        set_reset_cookie(response, result["reset_token"])
        # CSRF para el siguiente paso (reset-password) que usa cookie.
        set_csrf_cookie(response, generate_csrf_token())
        log_event(
            request,
            "RESET_CODE_VERIFIED",
            "SUCCESS",
            actor_user=result.get("user"),
            target_user=result.get("user"),
            meta={
                "endpoint": "/auth/verify-reset-code",
                "email": mask_email(serializer.validated_data.get("email")),
            },
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class ChangePasswordView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            user = authenticate_request(request)
        except AuthServiceError as exc:
            log_event(
                request,
                "PASSWORD_CHANGE_FAILED",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/change-password"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            log_event(
                request,
                "PASSWORD_CHANGE_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="PERMISSION_DENIED",
                meta={"endpoint": "/auth/change-password"},
            )
            return csrf_error

        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            log_event(
                request,
                "PASSWORD_CHANGE_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="VALIDATION_ERROR",
                meta={"endpoint": "/auth/change-password"},
            )
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        try:
            change_password(
                user,
                serializer.validated_data["currentPassword"],
                serializer.validated_data["newPassword"],
            )
        except AuthServiceError as exc:
            log_event(
                request,
                "PASSWORD_CHANGE_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code=exc.code,
                meta={"endpoint": "/auth/change-password"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )
        except Exception:
            log_event(
                request,
                "PASSWORD_CHANGE_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="INTERNAL_SERVER_ERROR",
                meta={"endpoint": "/auth/change-password"},
            )
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        log_event(
            request,
            "PASSWORD_CHANGE_SUCCESS",
            "SUCCESS",
            actor_user=user,
            target_user=user,
            meta={"endpoint": "/auth/change-password"},
        )

        # La clave ya cambio: se rota la sesion (cierra la vieja, emite cookies).
        try:
            access_token, refresh_token, _sid = rotate_user_session(
                user,
                get_client_ip(request),
                request.META.get("HTTP_USER_AGENT"),
            )
        except AuthServiceError:
            # La clave ya esta guardada: se responde 200 sin cookies nuevas.
            log_event(
                request,
                "PASSWORD_CHANGE_SESSION_ROTATION_FAILED",
                "FAIL",
                actor_user=user,
                target_user=user,
                error_code="SERVICE_UNAVAILABLE",
                meta={"endpoint": "/auth/change-password"},
            )
            return Response(
                {"success": True, "sessionRotated": False},
                status=status.HTTP_200_OK,
            )

        response = Response(
            {"success": True, "sessionRotated": True}, status=status.HTTP_200_OK
        )
        set_auth_cookies(response, access_token, refresh_token, generate_csrf_token())
        return response


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            log_event(
                request,
                "PASSWORD_RESET_FAILED",
                "FAIL",
                error_code="VALIDATION_ERROR",
                meta={"endpoint": "/auth/reset-password"},
            )
            return error_response(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
                request_id=get_request_id(request),
            )

        reset_token = request.COOKIES.get("reset_token")
        if not reset_token:
            log_event(
                request,
                "PASSWORD_RESET_FAILED",
                "FAIL",
                error_code="TOKEN_INVALID",
                meta={"endpoint": "/auth/reset-password"},
            )
            return error_response(
                "TOKEN_INVALID",
                "Token inválido",
                status.HTTP_401_UNAUTHORIZED,
                request_id=get_request_id(request),
            )

        csrf_error = _csrf_or_error(request)
        if csrf_error:
            log_event(
                request,
                "PASSWORD_RESET_FAILED",
                "FAIL",
                error_code="PERMISSION_DENIED",
                meta={"endpoint": "/auth/reset-password"},
            )
            return csrf_error

        try:
            result = reset_password(
                reset_token,
                serializer.validated_data["newPassword"],
                get_client_ip(request),
                request.META.get("HTTP_USER_AGENT"),
            )
        except AuthServiceError as exc:
            log_event(
                request,
                "PASSWORD_RESET_FAILED",
                "FAIL",
                error_code=exc.code,
                meta={"endpoint": "/auth/reset-password"},
            )
            return error_response(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
                request_id=get_request_id(request),
            )
        except Exception:
            log_event(
                request,
                "PASSWORD_RESET_FAILED",
                "FAIL",
                error_code="INTERNAL_SERVER_ERROR",
                meta={"endpoint": "/auth/reset-password"},
            )
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        response = Response(
            {
                "user": result["user"],
                "requiresOnboarding": bool(result["user"].get("requiresOnboarding")),
            },
            status=status.HTTP_200_OK,
        )
        # Cierra el flujo de reset con nueva sesion.
        csrf_token = generate_csrf_token()
        set_auth_cookies(
            response,
            result["access_token"],
            result["refresh_token"],
            csrf_token,
        )
        # Elimina cookie reset luego del cambio.
        clear_reset_cookie(response)
        log_event(
            request,
            "PASSWORD_RESET_SUCCESS",
            "SUCCESS",
            actor_user=UserRepository.get_by_id(result["user"]["id"]),
            target_user=UserRepository.get_by_id(result["user"]["id"]),
            meta={"endpoint": "/auth/reset-password"},
        )
        return response
