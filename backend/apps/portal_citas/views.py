"""
apps/portal_citas/views.py
=============================
Endpoints del portal de Citas en Línea.

Los 3 endpoints de autenticación (Fase 2) son públicos: sin sesión
iniciada todavía, así que ``authentication_classes = []`` /
``permission_classes = []`` (mismo patrón que las vistas públicas de
``apps.authentication.views`` y ``apps.recepcion``) — son el proceso de
login en sí mismo, ninguno requiere ``IsPortalUser``.

Los endpoints de Fase 3 (núcleo familiar, especialidades, slots), Fase 4
(reserva de citas), Fase 6 (cancelación) y Fase 8 (listado de citas) SÍ
requieren sesión de portal válida:
``authentication_classes = [PortalTokenAuthentication]`` +
``permission_classes = [IsPortalUser]``.

Fuera de alcance: check-in / validación de QR en recepción — eso es de la
Fase 7.
"""

import logging

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.response_service import (
    error_response,
    get_client_ip,
    get_request_id,
)
from apps.comunicados.serializers import AnuncioPortalSerializer
from apps.comunicados.uses_case.listar_anuncios_vigentes_use_case import (
    ListarAnunciosVigentesUseCase,
)
from apps.portal_citas.authentication import PortalTokenAuthentication
from apps.portal_citas.errors import PortalAuthError, PortalCancelacionError, PortalReservaError
from apps.portal_citas.permissions import IsPortalUser
from apps.portal_citas.serializers import (
    CancelarCitaSerializer,
    CapturarCorreoSerializer,
    IniciarSesionSerializer,
    ReservarCitaSerializer,
    VerificarCodigoSerializer,
)
from apps.portal_citas.services.consultorios_service import (
    clinica_del_miembro,
    listar_centros_en_linea,
    listar_consultorios_en_linea,
)
from apps.portal_citas.services.especialidades_service import listar_especialidades
from apps.portal_citas.services.nucleo_service import obtener_nucleo
from apps.portal_citas.services.slots_service import get_disponibilidad_mensual, get_slots_portal
from apps.portal_citas.throttling import PortalAuthRateThrottle
from apps.portal_citas.uses_case.cancelar_cita_usecase import cancelar_cita
from apps.portal_citas.uses_case.capturar_correo_usecase import capturar_correo
from apps.portal_citas.uses_case.iniciar_sesion_usecase import iniciar_sesion
from apps.portal_citas.uses_case.listar_citas_usecase import listar_citas
from apps.portal_citas.uses_case.reservar_cita_usecase import reservar_cita
from apps.portal_citas.uses_case.verificar_codigo_usecase import verificar_codigo

logger = logging.getLogger(__name__)


def _portal_error_response(
    request, exc: PortalAuthError | PortalReservaError | PortalCancelacionError
):
    return error_response(
        exc.code,
        exc.message,
        exc.status_code,
        details=exc.details,
        request_id=get_request_id(request),
    )


def _validar_input(serializer_cls, data, mensaje: str, request):
    """
    Valida ``data`` con ``serializer_cls`` y colapsa el patrón repetido
    ``if not serializer.is_valid(): return error_response(...)`` que se
    repite en todas las vistas del portal (tanto para query params de los
    endpoints GET como para el body de los POST/PATCH).

    Retorna ``(validated_data, None)`` si la validación pasa, o
    ``(None, Response)`` con el mismo error 422 estándar (``VALIDATION_ERROR``,
    mismos ``details``/``request_id``) que ya devolvía cada call-site. NO
    cambia comportamiento: cada call-site sigue pasando su propio mensaje.
    """
    serializer = serializer_cls(data=data)
    if not serializer.is_valid():
        return None, error_response(
            "VALIDATION_ERROR",
            mensaje,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=serializer.errors,
            request_id=get_request_id(request),
        )
    return serializer.validated_data, None


@method_decorator(csrf_exempt, name="dispatch")
class IniciarSesionView(APIView):
    """POST /portal/auth/iniciar-sesion"""

    authentication_classes = []
    permission_classes = []
    throttle_classes = [PortalAuthRateThrottle]

    def post(self, request):
        validated_data, err = _validar_input(
            IniciarSesionSerializer, request.data, "Hay errores en el formulario", request
        )
        if err:
            return err

        try:
            result = iniciar_sesion(
                validated_data["noExp"],
                validated_data["nombreCompleto"],
                validated_data["fechaNacimiento"],
            )
        except PortalAuthError as exc:
            return _portal_error_response(request, exc)
        except Exception:
            logger.exception("Error inesperado en iniciar-sesion del portal")
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        return Response(result, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class CapturarCorreoView(APIView):
    """POST /portal/auth/capturar-correo"""

    authentication_classes = []
    permission_classes = []
    throttle_classes = [PortalAuthRateThrottle]

    def post(self, request):
        validated_data, err = _validar_input(
            CapturarCorreoSerializer, request.data, "Hay errores en el formulario", request
        )
        if err:
            return err

        try:
            result = capturar_correo(
                validated_data["noExp"],
                validated_data["nombreCompleto"],
                validated_data["fechaNacimiento"],
                validated_data["correo"],
            )
        except PortalAuthError as exc:
            return _portal_error_response(request, exc)
        except Exception:
            logger.exception("Error inesperado en capturar-correo del portal")
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        return Response(result, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class VerificarCodigoView(APIView):
    """POST /portal/auth/verificar-codigo"""

    authentication_classes = []
    permission_classes = []
    throttle_classes = [PortalAuthRateThrottle]

    def post(self, request):
        validated_data, err = _validar_input(
            VerificarCodigoSerializer, request.data, "Hay errores en el formulario", request
        )
        if err:
            return err

        try:
            result = verificar_codigo(
                validated_data["noExp"],
                validated_data["nombreCompleto"],
                validated_data["fechaNacimiento"],
                validated_data["codigo"],
                ip_origen=get_client_ip(request),
            )
        except PortalAuthError as exc:
            return _portal_error_response(request, exc)
        except Exception:
            logger.exception("Error inesperado en verificar-codigo del portal")
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        return Response(
            {
                "accessToken": result["accessToken"],
                "tokenType": "Bearer",
                "expiraEn": result["expiraEn"].isoformat(),
            },
            status=status.HTTP_200_OK,
        )


# ── Fase 3: núcleo familiar y disponibilidad ────────────────────────────────


class SlotsPortalQuerySerializer(serializers.Serializer):
    fecha = serializers.DateField(input_formats=["%Y-%m-%d"])
    # camelCase para seguir la convención de query params del resto del
    # proyecto (medicoId, fechaDesde, pageSize en CreateCitaSerializer de
    # apps.recepcion). ``consultorioId`` es el eje de filtro efectivo del
    # portal nuevo (Disponibilidad por Consultorio); opcional para no
    # romper llamadas sin filtro.
    consultorioId = serializers.IntegerField(required=False, min_value=1)
    # DEPRECATED: se mantiene funcional durante una release de transición
    # para el cliente legado que aún manda solo especialidadId (ver
    # slots_service.get_slots_portal). Remover una release después de
    # desplegar el portal nuevo.
    especialidadId = serializers.IntegerField(required=False, min_value=1)


class NucleoView(APIView):
    """
    GET /portal/nucleo — pacientes que la sesión de portal autenticada
    puede ver y gestionar (ver reglas en ``services.nucleo_service``).
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request):
        nucleo = obtener_nucleo(request.portal_miembro)
        return Response({"nucleo": nucleo})


class EspecialidadesPortalView(APIView):
    """
    GET /portal/especialidades — catálogo de especialidades disponible
    para armar el selector del frontend (filtro de ``GET /portal/slots``).
    Solo lectura, no expone nada sensible.
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request):
        return Response({"especialidades": listar_especialidades()})


class AnunciosPortalView(APIView):
    """
    GET /portal/anuncios — anuncios/flyers vigentes (módulo Comunicados,
    change `anuncios-portal-citas`) para el banner del portal de citas.
    Requiere sesión de portal válida, mismo molde que
    ``EspecialidadesPortalView`` (decisión 9 del índice de arquitectura
    `architecture/anuncios-portal-citas`: NO es un endpoint público sin
    sesión). Nunca responde 404 -- lista vacía si no hay anuncios vigentes.
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request):
        anuncios = ListarAnunciosVigentesUseCase.execute(hoy=timezone.localdate())
        serializer = AnuncioPortalSerializer(anuncios, many=True)
        return Response({"anuncios": serializer.data})


class CentrosPortalView(APIView):
    """
    GET /portal/centros — catálogo de centros de atención (rotulados
    "Clínica" en la UI) con AL MENOS UN consultorio habilitado para canal
    en línea (ver ``services.consultorios_service.listar_centros_en_linea``),
    usado para armar el selector de clínica del frontend. Solo lectura, no
    expone nada sensible.

    El nombre en el wire es ``centroId`` (no ``clinicaId``): el dominio
    real es ``CatCentroAtencion``, y el payload de ``/portal/consultorios``
    ya expone ``centroNombre`` -- el wire sigue el nombre del dominio, la
    UI rotula "Clínica" (ver design doc de
    ``portal-citas-filtro-clinica``).
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request):
        validated_data, err = _validar_input(
            MiembroPortalQuerySerializer, request.query_params, "Parámetros inválidos.", request
        )
        if err:
            return err
        try:
            centro_paciente = _clinica_del_miembro(request, validated_data)
        except PortalReservaError as exc:
            return _portal_error_response(request, exc)
        return Response({"centros": listar_centros_en_linea(centro_paciente=centro_paciente)})


class MiembroPortalQuerySerializer(serializers.Serializer):
    # Paciente para el que se busca horario: limita el catálogo a su clínica.
    miembroId = serializers.UUIDField(required=False)


def _clinica_del_miembro(request, validated_data):
    miembro_id = validated_data.get("miembroId")
    if miembro_id is None:
        return None
    return clinica_del_miembro(request.portal_miembro, miembro_id)


class ConsultoriosPortalQuerySerializer(MiembroPortalQuerySerializer):
    # Mismo criterio que ``centroId`` inexistente/valor inválido de
    # ``SlotsPortalQuerySerializer.consultorioId``: entero >= 1, opcional.
    centroId = serializers.IntegerField(required=False, min_value=1)


class ConsultoriosPortalView(APIView):
    """
    GET /portal/consultorios?centroId= — catálogo de consultorios
    habilitados para canal en línea (ver ``services.consultorios_service``),
    usado para armar el selector del frontend y como eje de búsqueda de
    ``GET /portal/slots`` / disponibilidad mensual. Solo lectura, no
    expone nada sensible.

    ``centroId`` (opcional, entero >= 1) filtra por centro de atención --
    valor inválido responde 422; centro inexistente o sin consultorios
    online responde 200 con ``consultorios: []`` (mismo criterio
    anti-enumeración que ``DisponibilidadMensualView``, NUNCA 404).
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request):
        validated_data, err = _validar_input(
            ConsultoriosPortalQuerySerializer, request.query_params, "Parámetros inválidos.", request
        )
        if err:
            return err
        try:
            centro_paciente = _clinica_del_miembro(request, validated_data)
        except PortalReservaError as exc:
            return _portal_error_response(request, exc)

        consultorios = listar_consultorios_en_linea(
            centro_id=validated_data.get("centroId"),
            centro_paciente=centro_paciente,
        )
        return Response({"consultorios": consultorios})


class SlotsPortalView(APIView):
    """GET /portal/slots?fecha=YYYY-MM-DD&consultorioId=&especialidadId="""

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request):
        validated_data, err = _validar_input(
            SlotsPortalQuerySerializer, request.query_params, "Parámetros inválidos.", request
        )
        if err:
            return err

        slots = get_slots_portal(
            fecha=validated_data["fecha"],
            consultorio_id=validated_data.get("consultorioId"),
            especialidad_id=validated_data.get("especialidadId"),
        )
        return Response({"slots": slots})


class DisponibilidadMensualQuerySerializer(serializers.Serializer):
    # Rango amplio y deliberadamente permisivo (no atado a "hoy"): la
    # validación de negocio (mes ya pasado, fuera de la ventana de
    # generación de slots) simplemente no devuelve fechas, no es un error
    # de request. Los límites solo evitan valores absurdos (año 0, mes 99).
    anio = serializers.IntegerField(min_value=2020, max_value=2100)
    mes = serializers.IntegerField(min_value=1, max_value=12)


class DisponibilidadMensualView(APIView):
    """
    GET /portal/consultorios/{id}/disponibilidad-mensual?anio=&mes=

    Conteo agregado de slots disponibles por fecha para un consultorio y
    mes/año (ver ``services.slots_service.get_disponibilidad_mensual``).

    Un ``id`` de consultorio inexistente o no habilitado para canal en
    línea responde 200 con ``dias: []`` — NUNCA 404: un 404 permitiría
    enumerar qué IDs de consultorio existen en el sistema, y esa
    información no aporta nada al frontend (que solo necesita saber si
    hay o no cupo).
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request, consultorio_id):
        validated_data, err = _validar_input(
            DisponibilidadMensualQuerySerializer, request.query_params, "Parámetros inválidos.", request
        )
        if err:
            return err

        anio = validated_data["anio"]
        mes = validated_data["mes"]
        dias = get_disponibilidad_mensual(consultorio_id, anio, mes)

        return Response({
            "consultorioId": consultorio_id,
            "anio": anio,
            "mes": mes,
            "dias": dias,
        })


# ── Fase 4: reserva de cita / Fase 8: listado de citas ──────────────────────


@method_decorator(csrf_exempt, name="dispatch")
class ReservarCitaView(APIView):
    """
    POST /portal/citas — reserva un ``HorarioDisponible`` para un miembro
    del núcleo que la sesión actual puede gestionar (ver reglas en
    ``services.nucleo_service.puede_gestionar_miembro``).

    GET /portal/citas — (Fase 8, endpoint que faltó en las fases
    originales) lista las citas del núcleo familiar que la sesión actual
    puede gestionar (ver reglas en ``services.nucleo_service`` y
    ``uses_case.listar_citas_usecase``). Vive en la misma clase/ruta que el
    ``POST`` (mismo patrón que el resto de las vistas del portal, donde el
    verbo HTTP distingue la acción sobre el mismo recurso "citas" — no se
    agrega una ruta nueva en ``urls.py`` para no duplicar el path
    ``portal/citas``).

    ``csrf_exempt`` porque, igual que los endpoints de autenticación, el
    portal se autentica con Bearer token (no cookie de sesión) y nunca
    tendrá la cookie CSRF que ``CsrfViewMiddleware`` espera.
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def get(self, request):
        try:
            citas = listar_citas(request.portal_miembro)
        except Exception:
            logger.exception("Error inesperado al listar citas del portal")
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        return Response({"citas": citas})

    def post(self, request):
        validated_data, err = _validar_input(
            ReservarCitaSerializer, request.data, "Datos inválidos.", request
        )
        if err:
            return err

        try:
            result = reservar_cita(
                request.portal_miembro,
                validated_data["miembroId"],
                validated_data["slotId"],
                motivo=validated_data.get("motivo") or None,
            )
        except PortalReservaError as exc:
            return _portal_error_response(request, exc)
        except Exception:
            logger.exception("Error inesperado al reservar cita del portal")
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        return Response(result, status=status.HTTP_201_CREATED)


# ── Fase 6: cancelación de cita ──────────────────────────────────────────────


@method_decorator(csrf_exempt, name="dispatch")
class CancelarCitaView(APIView):
    """
    PATCH /portal/citas/{folio}/cancelar — cancela una cita del portal a
    nombre de un miembro del núcleo que la sesión actual puede gestionar
    (ver reglas en ``services.nucleo_service.puede_gestionar_miembro``).

    ``csrf_exempt`` por el mismo motivo que ``ReservarCitaView``: el portal
    se autentica con Bearer token, nunca con cookie de sesión.
    """

    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalUser]

    def patch(self, request, folio):
        validated_data, err = _validar_input(
            CancelarCitaSerializer, request.data, "Datos inválidos.", request
        )
        if err:
            return err

        try:
            result = cancelar_cita(
                request.portal_miembro,
                folio,
                motivo=validated_data.get("motivo") or None,
            )
        except PortalCancelacionError as exc:
            return _portal_error_response(request, exc)
        except Exception:
            logger.exception("Error inesperado al cancelar cita del portal")
            return error_response(
                "INTERNAL_SERVER_ERROR",
                "Error del servidor, intenta nuevamente",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=get_request_id(request),
            )

        return Response(result, status=status.HTTP_200_OK)
