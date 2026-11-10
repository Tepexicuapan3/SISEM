"""
CRUD de citas médicas.
Sigue el mismo patrón de autorización que views.py (visitas).
"""

import logging
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.response_service import error_response, get_request_id
from apps.authentication.services.session_service import authenticate_request
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.audit_service import log_event
from apps.authentication.services.authorization_service import has_capability
from apps.authentication.services.centro_scope import alcance_de
from apps.catalogos.models import MotivoCita
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.recepcion.models import CanalMovimiento, EstatusCita
from apps.recepcion.repositories.citas_repository import CitasRepository, _serialize_cita
from apps.recepcion.services.alcance_centro import (
    alcance_para_agendar,
    exigir_centro_para_agendar,
    exigir_en_alcance,
)
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.proximas_citas_usecase import list_proximas_citas
from apps.recepcion.uses_case.visit_queue_usecase import RECEPCION_WRITE_CAPABILITY
from apps.recepcion.uses_case.agendar_cita_usecase import agendar_cita
from apps.recepcion.uses_case.cita_historial_usecase import get_cita_historial
from apps.recepcion.uses_case.reprogramar_cita_usecase import reprogramar_cita
from apps.recepcion.views.adscripcion_views import operador_de_usuario

logger = logging.getLogger(__name__)

CITAS_READ_CAPABILITY  = "recepcion:citas:read"
CITAS_WRITE_CAPABILITY = "recepcion:citas:write"


# ── Helpers de autorización ───────────────────────────────────────────────────

def _auth(request):
    try:
        return authenticate_request(request), None
    except AuthServiceError as exc:
        return None, error_response(exc.code, exc.message, exc.status_code,
                                    request_id=get_request_id(request))


def _csrf(request):
    if validate_csrf(request):
        return None
    return error_response("PERMISSION_DENIED", "No tienes permiso para esta acción.",
                          status.HTTP_403_FORBIDDEN, request_id=get_request_id(request))


def _check_cap(user, capability):
    auth = UserRepository.build_auth_user(user)
    if not has_capability(auth.get("permissions", []), capability):
        raise VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso.", 403)


def _auditar_cita(request, user, action, result, *, cita_id=None, error_code=None, antes=None, despues=None):
    """Auditoría central (AuditoriaEvento): actor, request, IP, navegador y antes/después."""
    log_event(
        request, action, result, actor_user=user, error_code=error_code,
        meta={"module": "recepcion", "endpoint": request.path},
        resource_type="cita", resource_id=cita_id, datos_antes=antes, datos_despues=despues,
    )


def _resumen_cita(cita: dict) -> dict:
    # Sin datos personales del paciente: la cita se identifica por folio e id.
    return {
        "folio": cita.get("folio"), "estatus": cita.get("estatus"), "fechaHora": cita.get("fechaHora"),
        "medicoId": cita.get("medicoId"), "consultorioId": cita.get("consultorioId"),
        "origenCanal": cita.get("origenCanal"),
    }


def _domain_error(request, exc):
    return error_response(exc.code, exc.message, exc.status_code,
                          request_id=get_request_id(request))


def _cita_en_alcance(user, cita_id):
    """La cita, o VisitDomainError 404 si no existe o es de otro centro."""
    cita = CitasRepository.get_by_id(cita_id)
    if not cita:
        raise VisitDomainError("CITA_NOT_FOUND", "Cita no encontrada.", 404)
    exigir_en_alcance(alcance_de(user), cita.centro_id, code="CITA_NOT_FOUND", message="Cita no encontrada.")
    return cita


def _resolve_medico_or_404(medico_id_raw, request):
    """
    `medicoId` es CatMedico.id (No. Médico, contrato unificado
    medicos-id-no-medico). `MedicoRepository.resolve` resuelve SOLO por pk (sin
    fallback a id_usuario): un id inexistente da 404 en vez de agendar con la
    PERSONA EQUIVOCADA.

    Devuelve `(medico, None)` o `(None, error_response)`.
    """
    medico = MedicoRepository.resolve(medico_id_raw, request=request)
    if not medico:
        return None, error_response(
            "MEDICO_NOT_FOUND", "Médico no encontrado.",
            status.HTTP_404_NOT_FOUND, request_id=get_request_id(request),
        )
    return medico, None


# ── Serializers ───────────────────────────────────────────────────────────────

class CreateCitaSerializer(serializers.Serializer):
    # Plan contraer la llave vieja: idPaciente (desde C0); noExp/pkNum transitorio.
    idPaciente    = serializers.IntegerField(min_value=1, required=False)
    noExp         = serializers.CharField(max_length=20, required=False)
    pkNum         = serializers.IntegerField(min_value=0, default=0)
    medicoId      = serializers.IntegerField(min_value=1)
    consultorioId = serializers.IntegerField(min_value=1, required=False)
    fechaHora     = serializers.DateTimeField()
    duracionMin   = serializers.IntegerField(min_value=5, max_value=120, required=False, default=20)
    servicioTipo  = serializers.ChoiceField(
        choices=("medicina_general", "especialidad", "urgencias"),
        required=False,
        default="medicina_general",
    )
    motivo        = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notas         = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    # P-03: cita que reagenda una cancelada por cambio de consultorio familiar,
    # y motivo para agendar en un consultorio distinto al familiar.
    idCitaAfectada = serializers.IntegerField(min_value=1, required=False)
    excepcionConsultorioFamiliar = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        from apps.consulta_medica.services.paciente_entrada import resolver_paciente_en_datos

        return resolver_paciente_en_datos(attrs)


class ListCitasQuerySerializer(serializers.Serializer):
    page          = serializers.IntegerField(min_value=1, required=False, default=1)
    pageSize      = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    medicoId      = serializers.IntegerField(min_value=1, required=False)
    consultorioId = serializers.IntegerField(min_value=1, required=False)
    centroId      = serializers.IntegerField(min_value=1, required=False)
    noExp         = serializers.CharField(max_length=20, required=False)
    folio         = serializers.CharField(max_length=32, required=False)
    estatus       = serializers.ChoiceField(
        choices=("agendada", "confirmada", "atendida", "cancelada", "no_asistio"),
        required=False,
    )
    fechaDesde    = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])
    fechaHasta    = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])

    def validate(self, attrs):
        desde = attrs.get("fechaDesde")
        hasta = attrs.get("fechaHasta")
        if desde and hasta and desde > hasta:
            raise serializers.ValidationError(
                {"fechaHasta": "La fecha hasta debe ser mayor o igual a la fecha desde."}
            )
        return attrs


class UpdateEstatusSerializer(serializers.Serializer):
    estatus = serializers.ChoiceField(
        choices=("confirmada", "atendida", "cancelada", "no_asistio")
    )
    # Motivo tipificado (catálogo) — obligatorio para cancelada/no_asistio,
    # lo exige cita_state_machine_usecase.transition_cita_state
    # (CITA_MOTIVO_REQUERIDO). Reemplaza el texto libre original (ver
    # catálogo MotivoCita); `motivoDetalle` preserva el texto libre
    # complementario opcional.
    motivoCancelacionId = serializers.PrimaryKeyRelatedField(
        queryset=MotivoCita.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    motivoDetalle = serializers.CharField(max_length=255, required=False, allow_blank=True)


class SlotsQuerySerializer(serializers.Serializer):
    medicoId = serializers.IntegerField(min_value=1)
    fecha    = serializers.DateField(input_formats=["%Y-%m-%d"])


# ── Vistas ────────────────────────────────────────────────────────────────────

class CitasListCreateView(APIView):
    """
    GET  /citas              → Listar citas con filtros
    POST /citas              → Agendar nueva cita
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

        s = ListCitasQuerySerializer(data=request.query_params)
        if not s.is_valid():
            return error_response("VALIDATION_ERROR", "Parámetros inválidos.",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=s.errors, request_id=get_request_id(request))

        # `medicoId` (CatMedico.id) es un filtro opcional. Se resuelve contra
        # CatMedico; si no matchea
        # ningún médico, se usa un sentinel imposible (-1) para que el
        # filtro devuelva 0 resultados en vez de ignorarse silenciosamente
        # (list_paginated hace `if medico_id:` -- None se interpretaría
        # como "sin filtro" y devolvería TODAS las citas).
        medico_id_filtro = None
        medico_id_raw = s.validated_data.get("medicoId")
        if medico_id_raw is not None:
            medico_filtro = MedicoRepository.resolve(medico_id_raw, request=request)
            medico_id_filtro = medico_filtro.id if medico_filtro else -1

        items, total, total_pages = CitasRepository.list_paginated(
            page=s.validated_data["page"],
            page_size=s.validated_data["pageSize"],
            medico_id=medico_id_filtro,
            consultorio_id=s.validated_data.get("consultorioId"),
            centro_id=s.validated_data.get("centroId"),
            no_exp=s.validated_data.get("noExp"),
            folio=s.validated_data.get("folio"),
            estatus=s.validated_data.get("estatus"),
            fecha_desde=s.validated_data.get("fechaDesde"),
            fecha_hasta=s.validated_data.get("fechaHasta"),
            alcance=alcance_de(user),
        )

        return Response({
            "items":      items,
            "page":       s.validated_data["page"],
            "pageSize":   s.validated_data["pageSize"],
            "total":      total,
            "totalPages": total_pages,
        })

    def post(self, request):
        user, err = _auth(request)
        if err:
            return err
        csrf_err = _csrf(request)
        if csrf_err:
            return csrf_err
        try:
            _check_cap(user, CITAS_WRITE_CAPABILITY)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        s = CreateCitaSerializer(data=request.data)
        if not s.is_valid():
            return error_response("VALIDATION_ERROR", "Datos inválidos.",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=s.errors, request_id=get_request_id(request))

        # ── Alcance por centro: agendar en otro centro exige permiso ─────────
        #    Sin consultorio elegido, vale el del horario que ocuparía.
        consultorio_destino = s.validated_data.get("consultorioId") or CitasRepository.consultorio_del_horario(
            s.validated_data["medicoId"], s.validated_data["fechaHora"],
        )
        permisos = UserRepository.build_auth_user(user).get("permissions", [])
        try:
            exigir_centro_para_agendar(alcance_de(user, permisos), permisos, consultorio_destino)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        # `medicoId` es CatMedico.id; se valida su existencia (resolve solo
        # por pk) ANTES de agendar.
        medico, err = _resolve_medico_or_404(s.validated_data["medicoId"], request)
        if err:
            return err

        # El operador se arma solo si hace falta (excepción o reagendado de P-03).
        def operador():
            return operador_de_usuario(user)

        datos = s.validated_data
        try:
            cita = agendar_cita(
                no_exp=datos["noExp"],
                pk_num=datos.get("pkNum", 0),
                id_paciente=datos.get("idPaciente"),
                medico_id=medico.id,
                consultorio_id=datos.get("consultorioId"),
                fecha_hora=datos["fechaHora"],
                duracion_min=datos.get("duracionMin", 20),
                servicio_tipo=datos.get("servicioTipo", "medicina_general"),
                motivo=datos.get("motivo") or None,
                notas=datos.get("notas") or None,
                id_cita_afectada=datos.get("idCitaAfectada"),
                excepcion_consultorio_familiar=datos.get("excepcionConsultorioFamiliar"),
                created_by_id=UserRepository.build_auth_user(user).get("id"),
                operador=operador,
                request=request,
            )
        except VisitDomainError as exc:
            # Vigencia, clínica, P-03, horario no disponible o una regla al
            # abrir el paciente (p. ej. recién nacido pendiente de vincular):
            # su mensaje dice qué hacer, no un 500.
            _auditar_cita(request, user, "CitaAgendada", "FAILED", error_code=exc.code)
            return error_response(exc.code, exc.message, exc.status_code,
                                  details=exc.details or None, request_id=get_request_id(request))
        except Exception as exc:
            logger.exception("Error creando cita: %s", exc)
            return error_response("CITA_CREATE_ERROR", "No se pudo agendar la cita.",
                                  status.HTTP_500_INTERNAL_SERVER_ERROR,
                                  request_id=get_request_id(request))

        _auditar_cita(request, user, "CitaAgendada", "SUCCESS", cita_id=cita["id"], despues=_resumen_cita(cita))
        return Response(cita, status=status.HTTP_201_CREATED)


class CitaDetailView(APIView):
    """
    GET   /citas/<id>          → Detalle de cita
    PATCH /citas/<id>/estatus  → Cambiar estatus
    """

    authentication_classes = []
    permission_classes     = []

    def get(self, request, cita_id):
        user, err = _auth(request)
        if err:
            return err
        try:
            _check_cap(user, CITAS_READ_CAPABILITY)
            cita = _cita_en_alcance(user, cita_id)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        return Response(_serialize_cita(cita))


class CitaHistorialView(APIView):
    """GET /citas/<id>/historial → bitácora NOM-024 de la cita (alta y cambios de estatus)."""

    authentication_classes = []
    permission_classes     = []

    def get(self, request, cita_id):
        user, err = _auth(request)
        if err:
            return err
        try:
            _check_cap(user, CITAS_READ_CAPABILITY)
            cita = _cita_en_alcance(user, cita_id)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        return Response({"items": get_cita_historial(cita)})


class ReprogramarCitaSerializer(serializers.Serializer):
    fechaHora     = serializers.DateTimeField()
    # Vacío: el mismo médico (y su consultorio).
    medicoId      = serializers.IntegerField(min_value=1, required=False)
    consultorioId = serializers.IntegerField(min_value=1, required=False)
    motivoDetalle = serializers.CharField(max_length=255, required=False, allow_blank=True)
    excepcionConsultorioFamiliar = serializers.CharField(max_length=255, required=False, allow_blank=True)


class CitaReprogramarView(APIView):
    """POST /citas/<id>/reprogramar → cancela la cita y agenda la nueva enlazada, en un solo paso."""

    authentication_classes = []
    permission_classes     = []

    def post(self, request, cita_id):
        user, err = _auth(request)
        if err:
            return err
        csrf_err = _csrf(request)
        if csrf_err:
            return csrf_err
        try:
            _check_cap(user, CITAS_WRITE_CAPABILITY)
            cita = _cita_en_alcance(user, cita_id)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        s = ReprogramarCitaSerializer(data=request.data)
        if not s.is_valid():
            return error_response("VALIDATION_ERROR", "Datos inválidos.",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=s.errors, request_id=get_request_id(request))
        datos = s.validated_data

        medico_id = cita.medico_id
        if datos.get("medicoId"):
            medico, err = _resolve_medico_or_404(datos["medicoId"], request)
            if err:
                return err
            medico_id = medico.id

        # Alcance por centro del destino, igual que al agendar.
        consultorio_destino = datos.get("consultorioId") or (
            cita.consultorio_id if medico_id == cita.medico_id
            else CitasRepository.consultorio_del_horario(medico_id, datos["fechaHora"])
        )
        permisos = UserRepository.build_auth_user(user).get("permissions", [])
        antes = _resumen_cita(_serialize_cita(cita))
        try:
            exigir_centro_para_agendar(alcance_de(user, permisos), permisos, consultorio_destino)
            nueva = reprogramar_cita(
                cita_id=cita.id,
                fecha_hora=datos["fechaHora"],
                medico_id=medico_id,
                consultorio_id=datos.get("consultorioId"),
                motivo_detalle=datos.get("motivoDetalle") or None,
                excepcion_consultorio_familiar=datos.get("excepcionConsultorioFamiliar"),
                created_by_id=UserRepository.build_auth_user(user).get("id"),
                operador=lambda: operador_de_usuario(user),
                request=request,
                canal=CanalMovimiento.RECEPCION,
            )
        except VisitDomainError as exc:
            _auditar_cita(request, user, "CitaReprogramada", "FAILED", cita_id=cita.id,
                          error_code=exc.code, antes=antes)
            return error_response(exc.code, exc.message, exc.status_code,
                                  details=exc.details or None, request_id=get_request_id(request))

        _auditar_cita(request, user, "CitaReprogramada", "SUCCESS", cita_id=nueva["id"],
                      antes=antes, despues=_resumen_cita(nueva))
        return Response(nueva, status=status.HTTP_201_CREATED)


class CitaEstatusView(APIView):
    """PATCH /citas/<id>/estatus"""

    authentication_classes = []
    permission_classes     = []

    def patch(self, request, cita_id):
        user, err = _auth(request)
        if err:
            return err
        csrf_err = _csrf(request)
        if csrf_err:
            return csrf_err
        try:
            _check_cap(user, CITAS_WRITE_CAPABILITY)
            cita = _cita_en_alcance(user, cita_id)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        s = UpdateEstatusSerializer(data=request.data)
        if not s.is_valid():
            return error_response("VALIDATION_ERROR", "Estatus inválido.",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=s.errors, request_id=get_request_id(request))

        auth_user = UserRepository.build_auth_user(user)
        antes = {"estatus": cita.estatus}
        try:
            result = CitasRepository.update_estatus(
                cita,
                s.validated_data["estatus"],
                motivo_cancelacion=s.validated_data.get("motivoCancelacionId"),
                motivo_detalle=s.validated_data.get("motivoDetalle") or None,
                changed_by_id=auth_user.get("id"),
                canal=CanalMovimiento.RECEPCION,
            )
        except VisitDomainError as exc:
            _auditar_cita(request, user, "CitaEstatusCambiado", "FAILED", cita_id=cita.id,
                          error_code=exc.code, antes=antes)
            return _domain_error(request, exc)

        _auditar_cita(
            request, user, "CitaEstatusCambiado", "SUCCESS", cita_id=cita.id, antes=antes,
            despues={**_resumen_cita(result), "motivoDetalle": s.validated_data.get("motivoDetalle") or None},
        )
        return Response(result)


class MotivosCancelacionView(APIView):
    """
    GET /citas/motivos-cancelacion

    Motivos tipificados (catálogo MotivoCita) que aplican a una cancelación,
    para los diálogos de cancelar cita y cancelar ficha de recepción. El
    catálogo completo (/appointment-reasons/) exige permiso de admin de
    catálogos; aquí basta con poder trabajar la agenda o la cola.
    """

    authentication_classes = []
    permission_classes     = []

    def get(self, request):
        user, err = _auth(request)
        if err:
            return err
        permisos = UserRepository.build_auth_user(user).get("permissions", [])
        if not any(has_capability(permisos, cap) for cap in (
            CITAS_READ_CAPABILITY, CITAS_WRITE_CAPABILITY, RECEPCION_WRITE_CAPABILITY,
        )):
            return _domain_error(request, VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso.", 403))

        motivos = (
            MotivoCita.objects
            .filter(is_active=True, deleted_at__isnull=True,
                    aplica_a__in=(MotivoCita.AplicaA.CANCELACION, MotivoCita.AplicaA.AMBOS))
            .order_by("name")
            .values("id", "name")
        )
        return Response({"results": list(motivos)})


class SlotsDisponiblesView(APIView):
    """GET /citas/slots?medicoId=X&fecha=YYYY-MM-DD"""

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

        s = SlotsQuerySerializer(data=request.query_params)
        if not s.is_valid():
            return error_response("VALIDATION_ERROR", "Parámetros inválidos.",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=s.errors, request_id=get_request_id(request))

        # `medicoId` es CatMedico.id (contrato unificado).
        medico, err = _resolve_medico_or_404(s.validated_data["medicoId"], request)
        if err:
            return err
        medico_id = medico.id
        fecha     = s.validated_data["fecha"]

        permisos = UserRepository.build_auth_user(user).get("permissions", [])
        alcance = alcance_para_agendar(alcance_de(user, permisos), permisos)
        slots = CitasRepository.get_slots_disponibles(medico_id=medico_id, fecha=fecha, alcance=alcance)

        # Se regenera solo si el médico no tiene horarios, no si el alcance los oculta.
        if not slots and fecha >= date.today() and not CitasRepository.get_slots_disponibles(medico_id=medico_id, fecha=fecha):
            dias = (fecha - date.today()).days + 1
            CitasRepository.generar_slots_medico(medico_id=medico_id, dias_adelante=dias)
            slots = CitasRepository.get_slots_disponibles(medico_id=medico_id, fecha=fecha, alcance=alcance)

        return Response({"slots": slots})


# ── Próximas citas ───────────────────────────────────────────────────────────

# Tope del rango: un mes. La lista resuelve nombres en SERMED por página.
PROXIMAS_MAX_DIAS = 31


class ProximasCitasQuerySerializer(serializers.Serializer):
    page             = serializers.IntegerField(min_value=1, required=False, default=1)
    pageSize         = serializers.IntegerField(min_value=1, max_value=50, required=False, default=25)
    medicoId         = serializers.IntegerField(min_value=1, required=False)
    soloSeguimiento  = serializers.BooleanField(required=False, default=False)
    fechaDesde       = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])
    fechaHasta       = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])

    def validate(self, attrs):
        desde = attrs.get("fechaDesde") or timezone.localdate()
        hasta = attrs.get("fechaHasta") or desde + timedelta(days=7)
        if desde > hasta:
            raise serializers.ValidationError({"fechaHasta": "Debe ser igual o posterior a fechaDesde."})
        if (hasta - desde).days > PROXIMAS_MAX_DIAS:
            raise serializers.ValidationError(
                {"fechaHasta": f"El rango no puede ser mayor a {PROXIMAS_MAX_DIAS} días."}
            )
        attrs["fechaDesde"], attrs["fechaHasta"] = desde, hasta
        return attrs


class ProximasCitasView(APIView):
    """Citas agendadas o confirmadas de los próximos días, con el nombre del
    paciente y la marca de las de seguimiento (las que deja el médico)."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, err = _auth(request)
        if err:
            return err
        try:
            _check_cap(user, CITAS_READ_CAPABILITY)
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        s = ProximasCitasQuerySerializer(data=request.query_params)
        if not s.is_valid():
            return error_response("VALIDATION_ERROR", "Parámetros inválidos.",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=s.errors, request_id=get_request_id(request))

        # Mismo criterio que el listado: un medicoId que no existe no devuelve nada.
        medico_id = None
        if s.validated_data.get("medicoId") is not None:
            medico = MedicoRepository.resolve(s.validated_data["medicoId"], request=request)
            medico_id = medico.id if medico else -1

        items, total, total_pages = list_proximas_citas(
            alcance_de(user),
            fecha_desde=s.validated_data["fechaDesde"],
            fecha_hasta=s.validated_data["fechaHasta"],
            page=s.validated_data["page"],
            page_size=s.validated_data["pageSize"],
            medico_id=medico_id,
            solo_seguimiento=s.validated_data["soloSeguimiento"],
        )
        return Response({
            "items":      items,
            "page":       s.validated_data["page"],
            "pageSize":   s.validated_data["pageSize"],
            "total":      total,
            "totalPages": total_pages,
        })
