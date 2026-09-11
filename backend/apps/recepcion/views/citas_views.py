"""
CRUD de citas médicas.
Sigue el mismo patrón de autorización que views.py (visitas).
"""

import logging
from datetime import date

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.response_service import error_response, get_request_id
from apps.authentication.services.session_service import authenticate_request
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.authorization_service import has_capability
from apps.catalogos.models import MotivoCita
from apps.medicos.views.medico_views import resolve_medico
from apps.recepcion.models import CitaMedica, EstatusCita
from apps.recepcion.repositories.citas_repository import CitasRepository, _serialize_cita
from apps.recepcion.services.errors import VisitDomainError

logger = logging.getLogger(__name__)

CITAS_READ_CAPABILITY  = "recepcion:citas:read"
CITAS_WRITE_CAPABILITY = "recepcion:citas:write"


# ── Validación de clínica ─────────────────────────────────────────────────────

def _validar_clinica_paciente(no_exp: str, pk_num: int, consultorio_id: int) -> None:
    """
    Verifica que el paciente (empleado o derechohabiente) pertenece al
    centro de atención del consultorio seleccionado.

    Compara cd_clinica de SERMED con legacy_folio de cat_centros_atencion.
    Lanza VisitDomainError si no coinciden.
    """
    from apps.administracion.use_cases.expedientes.buscar_expediente import buscar_expediente
    from apps.catalogos.models.consultorios import Consultorios

    # 1. Obtener cd_clinica del paciente desde SERMED
    resultado  = buscar_expediente(no_exp)
    empleados  = resultado.get("empleados", [])
    familiares = resultado.get("familiares", [])

    cd_clinica = None
    if pk_num == 0 and empleados:
        cd_clinica = empleados[0].get("CD_CLINICA")
    elif pk_num > 0:
        fam = next((f for f in familiares if f.get("PK_NUM") == pk_num), None)
        if fam:
            cd_clinica = fam.get("CD_CLINICA")

    if not cd_clinica:
        return  # Sin dato de clínica en SERMED → no bloqueamos

    # 2. Obtener el id del centro al que pertenece el consultorio
    consultorio = (
        Consultorios.objects
        .select_related("id_center")
        .filter(id=consultorio_id)
        .first()
    )
    if not consultorio or not consultorio.id_center:
        return  # Sin centro asignado → no bloqueamos

    # cd_clinica de SERMED coincide con id (PK) del CatCentroAtencion
    id_centro = consultorio.id_center.id

    # 3. Comparar (ambos como string para evitar diferencias de tipo)
    if str(cd_clinica).strip() != str(id_centro).strip():
        raise VisitDomainError(
            "WRONG_CLINIC",
            f"El paciente pertenece a la clínica {cd_clinica} y no puede "
            f"agendar cita en este centro de atención.",
            400,
        )


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


def _domain_error(request, exc):
    return error_response(exc.code, exc.message, exc.status_code,
                          request_id=get_request_id(request))


def _resolve_medico_or_404(medico_id_raw, request):
    """
    Gap 10.3 (design, topic sdd/medico-pk-independiente/design): `medicoId`
    llega crudo del frontend, que todavía manda el `id` legacy (id_usuario)
    porque no fue migrado. Se resuelve contra CatMedico con el mismo patrón
    que `medicos/views/medico_views.py::resolve_medico` (PK surrogate
    primero, fallback a id_usuario con WARN) en vez de pasar el valor sin
    traducir a CitasRepository -- evita agendar/buscar horarios de la
    PERSONA EQUIVOCADA (R1).

    Devuelve `(medico, None)` o `(None, error_response)`.
    """
    medico = resolve_medico(medico_id_raw, request=request)
    if not medico:
        return None, error_response(
            "MEDICO_NOT_FOUND", "Médico no encontrado.",
            status.HTTP_404_NOT_FOUND, request_id=get_request_id(request),
        )
    return medico, None


# ── Serializers ───────────────────────────────────────────────────────────────

class CreateCitaSerializer(serializers.Serializer):
    noExp         = serializers.CharField(max_length=20)
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

        # Gap 10.3: `medicoId` es un filtro opcional que llega crudo del
        # frontend (id legacy). Se resuelve contra CatMedico; si no matchea
        # ningún médico, se usa un sentinel imposible (-1) para que el
        # filtro devuelva 0 resultados en vez de ignorarse silenciosamente
        # (list_paginated hace `if medico_id:` -- None se interpretaría
        # como "sin filtro" y devolvería TODAS las citas).
        medico_id_filtro = None
        medico_id_raw = s.validated_data.get("medicoId")
        if medico_id_raw is not None:
            medico_filtro = resolve_medico(medico_id_raw, request=request)
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

        # ── Validar que el paciente pertenece al centro de la cita ───────────
        consultorio_id = s.validated_data.get("consultorioId")
        if consultorio_id:
            try:
                _validar_clinica_paciente(
                    no_exp=s.validated_data["noExp"],
                    pk_num=s.validated_data.get("pkNum", 0),
                    consultorio_id=consultorio_id,
                )
            except VisitDomainError as exc:
                return _domain_error(request, exc)

        # Gap 10.3: `medicoId` llega crudo del frontend (id legacy) -- se
        # resuelve a la PK surrogate de CatMedico ANTES de pasarlo a
        # CitasRepository.create, mismo patrón que resolve_medico en
        # medico_views.py.
        medico, err = _resolve_medico_or_404(s.validated_data["medicoId"], request)
        if err:
            return err

        auth_user = UserRepository.build_auth_user(user)
        try:
            cita = CitasRepository.create(
                no_exp=s.validated_data["noExp"],
                pk_num=s.validated_data.get("pkNum", 0),
                medico_id=medico.id,
                consultorio_id=s.validated_data.get("consultorioId"),
                fecha_hora=s.validated_data["fechaHora"],
                duracion_min=s.validated_data.get("duracionMin", 20),
                servicio_tipo=s.validated_data.get("servicioTipo", "medicina_general"),
                motivo=s.validated_data.get("motivo") or None,
                notas=s.validated_data.get("notas") or None,
                created_by_id=auth_user.get("id"),
            )
        except ValueError as exc:
            return error_response("CITA_NOT_AVAILABLE", str(exc),
                                  status.HTTP_400_BAD_REQUEST,
                                  request_id=get_request_id(request))
        except Exception as exc:
            logger.exception("Error creando cita: %s", exc)
            return error_response("CITA_CREATE_ERROR", "No se pudo agendar la cita.",
                                  status.HTTP_500_INTERNAL_SERVER_ERROR,
                                  request_id=get_request_id(request))

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
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        cita = CitasRepository.get_by_id(cita_id)
        if not cita:
            return error_response("CITA_NOT_FOUND", "Cita no encontrada.",
                                  status.HTTP_404_NOT_FOUND,
                                  request_id=get_request_id(request))

        return Response(_serialize_cita(cita))


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
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        cita = CitasRepository.get_by_id(cita_id)
        if not cita:
            return error_response("CITA_NOT_FOUND", "Cita no encontrada.",
                                  status.HTTP_404_NOT_FOUND,
                                  request_id=get_request_id(request))

        s = UpdateEstatusSerializer(data=request.data)
        if not s.is_valid():
            return error_response("VALIDATION_ERROR", "Estatus inválido.",
                                  status.HTTP_422_UNPROCESSABLE_ENTITY,
                                  details=s.errors, request_id=get_request_id(request))

        auth_user = UserRepository.build_auth_user(user)
        try:
            result = CitasRepository.update_estatus(
                cita,
                s.validated_data["estatus"],
                motivo_cancelacion=s.validated_data.get("motivoCancelacionId"),
                motivo_detalle=s.validated_data.get("motivoDetalle") or None,
                changed_by_id=auth_user.get("id"),
            )
        except VisitDomainError as exc:
            return _domain_error(request, exc)

        return Response(result)


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

        # Gap 10.3: `medicoId` llega crudo del frontend (id legacy).
        medico, err = _resolve_medico_or_404(s.validated_data["medicoId"], request)
        if err:
            return err
        medico_id = medico.id
        fecha     = s.validated_data["fecha"]

        slots = CitasRepository.get_slots_disponibles(medico_id=medico_id, fecha=fecha)

        if not slots and fecha >= date.today():
            dias = (fecha - date.today()).days + 1
            CitasRepository.generar_slots_medico(medico_id=medico_id, dias_adelante=dias)
            slots = CitasRepository.get_slots_disponibles(medico_id=medico_id, fecha=fecha)

        return Response({"slots": slots})
