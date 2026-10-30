"""
Verificación de QR del comprobante de cita y confirmación de check-in — Fase 7
del módulo "Citas en Línea". También expone el check-in manual (sin QR) por
nombre de paciente o folio de la cita — mismo flujo de negocio
(``checkin_por_folio``), solo cambia cómo se resuelve el folio.

POST /citas/verificar-qr           → valida el payload firmado del QR y
                                       devuelve los datos de la ficha para
                                       que recepción confirme visualmente.
POST /citas/verificar-qr/confirmar → confirma el check-in: crea el Visit
                                       (reusando create_visit) y marca la
                                       cita como verificada.
GET  /citas/checkin/candidatos     → busca citas de HOY elegibles para
                                       check-in por nombre (substring) o por
                                       folio exacto — exactamente uno de los
                                       dos parámetros.
POST /citas/checkin/confirmar-folio → confirma el check-in a partir de un
                                       folio ya resuelto (sin payload QR).

Sigue el mismo patrón de autenticación/autorización que el resto de
``apps/recepcion`` (autenticación interna de staff vía cookie/JWT,
``authenticate_request`` + capabilities), NO ``PortalTokenAuthentication``
(esa es para el portal del paciente, este endpoint lo usa personal de
recepción logueado normalmente).
"""

import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.audit_service import log_event
from apps.authentication.services.authorization_service import has_capability
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.response_service import error_response, get_request_id
from apps.authentication.services.session_service import authenticate_request
from apps.realtime.events import publish_visit_created, publish_visit_status_changed
from apps.recepcion.serializers import (
    CandidatosCheckinQuerySerializer,
    ConfirmarCheckinFolioSerializer,
    ConfirmarQRCheckinSerializer,
    VerificarQRSerializer,
)
from apps.portal_citas.services.comprobante_service import verificar_payload_qr
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.adscripcion_usecase import validar_cita_en_checkin
from apps.recepcion.views.adscripcion_views import operador_de_usuario
from apps.recepcion.uses_case.qr_checkin_usecase import (
    CITAS_READ_CAPABILITY,
    RECEPCION_WRITE_CAPABILITY,
    buscar_candidatos_checkin,
    checkin_por_folio,
    confirmar_checkin,
    verificar_qr,
)

logger = logging.getLogger(__name__)


def _auth(request):
    try:
        return authenticate_request(request), None
    except AuthServiceError as exc:
        return None, error_response(
            exc.code, exc.message, exc.status_code,
            details=exc.details, request_id=get_request_id(request),
        )


def _csrf(request):
    if validate_csrf(request):
        return None
    return error_response(
        "PERMISSION_DENIED", "No tienes permiso para esta acción.",
        status.HTTP_403_FORBIDDEN, request_id=get_request_id(request),
    )


def _check_cap(user, capability):
    auth_user = UserRepository.build_auth_user(user)
    if not has_capability(auth_user.get("permissions", []), capability):
        raise VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso.", 403)


def _domain_error(request, exc):
    return error_response(
        exc.code, exc.message, exc.status_code,
        details=exc.details, request_id=get_request_id(request),
    )


def _validate_body(request, serializer_cls, data=None):
    """
    Valida ``data`` (por defecto ``request.data``) con ``serializer_cls``.
    Colapsa el patrón de validación repetido en las 4 vistas de este módulo
    (``VerificarQRView``, ``ConfirmarQRCheckinView``, ``CheckinCandidatosView``,
    ``ConfirmarCheckinPorFolioView``). Retorna ``(validated_data, None)`` si
    es válido, o ``(None, Response)`` con el mismo error 422 estándar que
    devolvía cada call-site (mismo código, status y formato).
    """
    if data is None:
        data = request.data
    s = serializer_cls(data=data)
    if not s.is_valid():
        return None, error_response(
            "VALIDATION_ERROR", "Datos inválidos.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=s.errors, request_id=get_request_id(request),
        )
    return s.validated_data, None


@method_decorator(csrf_exempt, name="dispatch")
class VerificarQRView(APIView):
    """POST /citas/verificar-qr — valida el QR y muestra la ficha para confirmar."""

    authentication_classes = []
    permission_classes     = []

    def post(self, request):
        user, err = _auth(request)
        if err:
            return err
        try:
            _check_cap(user, CITAS_READ_CAPABILITY)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        validated_data, err = _validate_body(request, VerificarQRSerializer)
        if err:
            return err
        payload = validated_data["payload"]

        try:
            ficha = verificar_qr(payload)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        return Response(ficha, status=status.HTTP_200_OK)


def _log_y_notificar_checkin(request, user, resultado: dict, origen: str) -> None:
    """
    Auditoría + evento realtime compartidos por los dos endpoints que
    terminan en un check-in efectivo (``checkin_por_folio`` bajo el capó):
    confirmación por QR y confirmación por folio directo. Solo cambia
    ``origen`` para que la auditoría distinga de dónde vino el check-in.
    """
    visit = resultado["visit"]
    log_event(
        request, "VisitCreated", "SUCCESS", actor_user=user,
        meta={
            "module": "recepcion", "endpoint": request.path,
            "visitId": visit.get("id"), "origen": origen,
            "folio": resultado.get("folio"),
            # Atendido sin vigencia por orden de Capital Humano.
            "autorizacionCapitalHumano": bool(resultado.get("autorizacionVigencia")),
        },
    )
    try:
        publish_visit_status_changed(
            visit_id=visit.get("id"), status=visit.get("status"),
            request_id=get_request_id(request), correlation_id=get_request_id(request),
        )
        publish_visit_created(
            visit_id=visit.get("id"), status=visit.get("status"),
            request_id=get_request_id(request), correlation_id=get_request_id(request),
        )
    except Exception:
        logger.exception(
            "No se pudo publicar evento realtime de check-in (%s)", origen,
            extra={"visitId": visit.get("id")},
        )


@method_decorator(csrf_exempt, name="dispatch")
class ConfirmarQRCheckinView(APIView):
    """POST /citas/verificar-qr/confirmar — confirma el check-in y crea la visita."""

    authentication_classes = []
    permission_classes     = []

    def post(self, request):
        user, err = _auth(request)
        if err:
            return err
        csrf_err = _csrf(request)
        if csrf_err:
            return csrf_err
        try:
            _check_cap(user, RECEPCION_WRITE_CAPABILITY)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        validated_data, err = _validate_body(request, ConfirmarQRCheckinSerializer)
        if err:
            return err
        payload = validated_data["payload"]

        # P-03 (A2/A3): si el QR no es válido, confirmar_checkin responde como siempre.
        folio = verificar_payload_qr(payload)
        if folio:
            try:
                validar_cita_en_checkin(
                    folio=folio,
                    excepcion_motivo=validated_data.get("excepcionConsultorioFamiliar"),
                    operador=lambda: operador_de_usuario(user),
                    request=request,
                )
            except VisitDomainError as exc:
                return _domain_error(request, exc)

        try:
            resultado = confirmar_checkin(
                payload,
                verificado_por_id=getattr(user, "id_usuario", None),
                autorizacion_capital_humano=validated_data.get("autorizacionCapitalHumano"),
            )
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        _log_y_notificar_checkin(request, user, resultado, origen="qr_checkin")
        return Response(resultado, status=status.HTTP_201_CREATED)


class CheckinCandidatosView(APIView):
    """
    GET /citas/checkin/candidatos?nombre=<texto>
    GET /citas/checkin/candidatos?folio=<folio>

    Busca citas de HOY elegibles para check-in manual (sin QR) por nombre
    del paciente (substring, case-insensitive) o por folio exacto —
    exactamente uno de los dos parámetros. Solo lectura, misma capability
    que ``VerificarQRView``.
    """

    authentication_classes = []
    permission_classes     = []

    def get(self, request):
        user, err = _auth(request)
        if err:
            return err
        try:
            _check_cap(user, CITAS_READ_CAPABILITY)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        validated_data, err = _validate_body(
            request, CandidatosCheckinQuerySerializer, data=request.query_params
        )
        if err:
            return err

        candidatos = buscar_candidatos_checkin(
            nombre=validated_data["nombre"],
            folio=validated_data["folio"],
        )
        return Response({"candidatos": candidatos}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ConfirmarCheckinPorFolioView(APIView):
    """
    POST /citas/checkin/confirmar-folio — confirma el check-in a partir de un
    folio ya resuelto (búsqueda por nombre o folio tipeado directo), sin
    payload QR. Mismo response shape que ``ConfirmarQRCheckinView``.
    """

    authentication_classes = []
    permission_classes     = []

    def post(self, request):
        user, err = _auth(request)
        if err:
            return err
        csrf_err = _csrf(request)
        if csrf_err:
            return csrf_err
        try:
            _check_cap(user, RECEPCION_WRITE_CAPABILITY)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        validated_data, err = _validate_body(request, ConfirmarCheckinFolioSerializer)
        if err:
            return err

        # P-03 (A2/A3): medicina general en el consultorio familiar, salvo excepción.
        try:
            validar_cita_en_checkin(
                folio=validated_data["folio"],
                excepcion_motivo=validated_data.get("excepcionConsultorioFamiliar"),
                operador=lambda: operador_de_usuario(user),
                request=request,
            )
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        try:
            resultado = checkin_por_folio(
                validated_data["folio"],
                verificado_por_id=getattr(user, "id_usuario", None),
                autorizacion_capital_humano=validated_data.get("autorizacionCapitalHumano"),
            )
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        _log_y_notificar_checkin(request, user, resultado, origen="folio_directo")
        return Response(resultado, status=status.HTTP_201_CREATED)
