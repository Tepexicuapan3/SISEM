"""
P-03 · API de la adscripción a consultorio familiar (/api/v1/adscripcion/...).

Transporte nada más: sesión por cookie, CSRF en escrituras, permiso atómico,
validación de entrada y respuesta en camelCase. La regla de negocio vive en
services/adscripcion_evaluacion.py y uses_case/adscripcion_*usecase.py.
"""

from django.db.models import Count, Q
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.models import DetUsuario
from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.authorization_service import has_capability
from apps.authentication.services.csrf_service import validate_csrf
from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.response_service import error_response, get_request_id
from apps.authentication.services.session_service import authenticate_request
from apps.consulta_medica.models import Patient
from apps.recepcion.models import (
    AdscripcionCitaAfectada,
    AdscripcionClinicaCentro,
    AdscripcionConsultorio,
    AdscripcionPaciente,
)
from apps.recepcion.services.adscripcion_evaluacion import evaluar_adscripcion, sugerir_consultorios
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case import adscripcion_config_usecase as config_usecase
from apps.recepcion.uses_case.adscripcion_usecase import (
    AdscripcionError,
    Operador,
    adscribir,
    descartar_cita_afectada,
    previsualizar,
)

PERMISO_LEER = "recepcion:consultorio_familiar:read"
PERMISO_ESCRIBIR = "recepcion:consultorio_familiar:write"
PERMISO_TODOS_CENTROS = "recepcion:consultorio_familiar:todos_centros"
PERMISO_EXCEPCION = "recepcion:consultorio_familiar:excepcion"
PERMISO_CONFIG = "admin:catalogos:consultorio_familiar:config"


def operador_de_usuario(user, permisos=None) -> Operador:
    """Quién opera: su centro (det_usuarios) y lo que sus permisos le dejan hacer."""
    if permisos is None:
        permisos = UserRepository.build_auth_user(user).get("permissions", [])
    centro = DetUsuario.objects.filter(id_usuario=user).values_list("id_centro_atencion_id", flat=True).first()
    return Operador(
        usuario=user,
        id_centro_atencion=centro,
        todos_centros=has_capability(permisos, PERMISO_TODOS_CENTROS),
        puede_excepcion=has_capability(permisos, PERMISO_EXCEPCION),
    )


# ── Transporte ───────────────────────────────────────────────────────────────

class _Rechazo(Exception):
    def __init__(self, respuesta):
        self.respuesta = respuesta


def _error(request, code, message, http_status, details=None):
    return error_response(code, message, http_status, details=details, request_id=get_request_id(request))


def _operador(request, capacidad, *, escritura=False) -> Operador:
    """Sesión, CSRF (en escrituras) y permiso; devuelve quién opera."""
    try:
        user = authenticate_request(request)
    except AuthServiceError as exc:
        raise _Rechazo(_error(request, exc.code, exc.message, exc.status_code)) from exc
    if escritura and not validate_csrf(request):
        raise _Rechazo(_error(request, "PERMISSION_DENIED", "No tienes permiso para esta acción.", 403))
    permisos = UserRepository.build_auth_user(user).get("permissions", [])
    if not has_capability(permisos, capacidad):
        raise _Rechazo(_error(request, "ROLE_NOT_ALLOWED", "No tienes permiso.", 403))
    return operador_de_usuario(user, permisos)


def _validar(request, serializer_class, data):
    s = serializer_class(data=data)
    if not s.is_valid():
        raise _Rechazo(_error(request, "VALIDATION_ERROR", "Datos inválidos.", 422, details=s.errors))
    return s.validated_data


def _responder(request, accion):
    """Ejecuta la acción y traduce rechazos y errores de negocio a error_response."""
    try:
        return accion()
    except _Rechazo as rechazo:
        return rechazo.respuesta
    except VisitDomainError as exc:
        return _error(request, exc.code, exc.message, exc.status_code, details=exc.details or None)


def _paciente_o_404(id_paciente):
    paciente = Patient.objects.filter(pk=id_paciente).first()
    if paciente is None:
        raise AdscripcionError("PACIENTE_NO_ENCONTRADO", "Paciente no encontrado.", 404)
    return paciente


# ── Representación ───────────────────────────────────────────────────────────

def _adscripcion(a):
    if a is None:
        return None
    return {
        "idAdscripcion": a.id,
        "idPaciente": a.paciente_id,
        "idCentroAtencion": a.centro_id,
        "centro": a.centro.name,
        "claveClinicaSermed": a.clave_clinica_sermed,
        "idConsultorio": a.consultorio_id,
        "consultorio": a.consultorio.name,
        "numeroConsultorio": a.consultorio.numero,
        "idTurno": a.turno_id,
        "turno": a.turno.name,
        "estatus": a.estatus,
        "origen": a.origen,
        "fueSugerida": a.fue_sugerida,
        "motivoCierre": a.motivo_cierre,
        "observaciones": a.observaciones,
        "fechaInicio": a.fecha_inicio.isoformat(),
        "fechaFin": a.fecha_fin.isoformat() if a.fecha_fin else None,
    }


def _cita(c):
    return {
        "idCita": c.id,
        "folio": c.folio,
        "fechaHora": c.fecha_hora.isoformat(),
        "estatus": c.estatus,
        "idConsultorio": c.consultorio_id,
        "consultorio": c.consultorio.name if c.consultorio_id else None,
        "idMedico": c.medico_id,
    }


def _cita_afectada(a):
    return {
        "idCitaAfectada": a.id,
        "idAdscripcion": a.adscripcion_id,
        # Dónde reagendar: el consultorio de la adscripción que la canceló.
        "idPaciente": a.adscripcion.paciente_id,
        "idConsultorioNuevo": a.adscripcion.consultorio_id,
        "consultorioNuevo": a.adscripcion.consultorio.name,
        "idCentroAtencion": a.adscripcion.centro_id,
        "estatus": a.estatus,
        "citaCancelada": _cita(a.cita_cancelada),
        "idCitaNueva": a.cita_nueva_id,
        "motivoDescarte": a.motivo_descarte,
        "fechaCreacion": a.fecha_creacion.isoformat(),
    }


def _opcion(o):
    return {
        "consultorioId": o.consultorio_id,
        "consultorio": o.nombre,
        "numero": o.numero,
        "turnoId": o.turno_id,
        "turno": o.turno,
        "carga": o.carga,
        "capacidadMaxima": o.capacidad_maxima,
        "esDeLaFamilia": o.es_de_la_familia,
        "sugerida": o.sugerida,
    }


def _equivalencia(e):
    return {
        "idClinicaCentro": e.id,
        "claveClinicaSermed": e.clave_clinica_sermed,
        "idCentroAtencion": e.centro_id,
        "centro": e.centro.name,
        "estaActivo": e.esta_activo,
    }


def _config_consultorio(c, carga=None):
    return {
        "idAdscripcionConsultorio": c.id,
        "consultorioId": c.consultorio_id,
        "consultorio": c.consultorio.name,
        "numero": c.consultorio.numero,
        "idCentroAtencion": c.consultorio.id_center_id,
        "turno": c.consultorio.id_turn.name,
        "capacidadMaxima": c.capacidad_maxima,
        "estaActivo": c.esta_activo,
        "carga": carga,
    }


# ── Entradas ─────────────────────────────────────────────────────────────────

class OpcionesQuerySerializer(serializers.Serializer):
    idPaciente = serializers.IntegerField(min_value=1)
    turnoId = serializers.IntegerField(min_value=1, required=False)


class PrevisualizarSerializer(serializers.Serializer):
    idPaciente = serializers.IntegerField(min_value=1)
    consultorioId = serializers.IntegerField(min_value=1)


class AdscribirSerializer(serializers.Serializer):
    idPaciente = serializers.IntegerField(min_value=1)
    consultorioId = serializers.IntegerField(min_value=1)
    idAdscripcionEsperada = serializers.IntegerField(min_value=1, allow_null=True)
    citasACancelar = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)
    motivoCancelacionId = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    origen = serializers.ChoiceField(choices=AdscripcionPaciente.Origen.values)
    fueSugerida = serializers.BooleanField(required=False, default=False)
    observaciones = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)


class CitasPorReagendarQuerySerializer(serializers.Serializer):
    """Sin filtros: las del centro de quien opera (bandeja de Agenda)."""

    idPaciente = serializers.IntegerField(min_value=1, required=False)
    centroId = serializers.IntegerField(min_value=1, required=False)


class DescartarSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255, allow_blank=True)


class EquivalenciaCrearSerializer(serializers.Serializer):
    claveClinicaSermed = serializers.CharField(max_length=10)
    idCentroAtencion = serializers.IntegerField(min_value=1)


class EquivalenciaCambiarSerializer(serializers.Serializer):
    idCentroAtencion = serializers.IntegerField(min_value=1, required=False)
    estaActivo = serializers.BooleanField(required=False)


class ConsultorioCrearSerializer(serializers.Serializer):
    consultorioId = serializers.IntegerField(min_value=1)
    capacidadMaxima = serializers.IntegerField(required=False, allow_null=True, default=None)


class ConsultorioCambiarSerializer(serializers.Serializer):
    capacidadMaxima = serializers.IntegerField(required=False, allow_null=True)
    estaActivo = serializers.BooleanField(required=False)


class ConsultoriosQuerySerializer(serializers.Serializer):
    centroId = serializers.IntegerField(min_value=1, required=False)


# ── Vistas de recepción ──────────────────────────────────────────────────────

class _Base(APIView):
    authentication_classes = []
    permission_classes = []


class AdscripcionPacienteView(_Base):
    """GET /adscripcion/pacientes/<id> → estado, adscripción y citas afectadas."""

    def get(self, request, id_paciente):
        def accion():
            _operador(request, PERMISO_LEER)
            paciente = _paciente_o_404(id_paciente)
            evaluacion = evaluar_adscripcion(paciente)
            pendientes = AdscripcionCitaAfectada.objects.filter(
                adscripcion__paciente=paciente, estatus=AdscripcionCitaAfectada.Estatus.PENDIENTE,
            ).count()
            return Response({
                "idPaciente": paciente.pk,
                "estado": evaluacion.estado,
                "requiereReasignar": evaluacion.requiere_reasignar,
                "claveClinicaSermed": evaluacion.clave_clinica_sermed,
                "idCentroSermed": evaluacion.centro_sermed_id,
                "adscripcion": _adscripcion(evaluacion.adscripcion),
                "sinMedicoActivo": evaluacion.sin_medico_activo,
                "citasFuturas": [_cita(c) for c in evaluacion.citas_futuras],
                "citasPorReagendar": pendientes,
            })
        return _responder(request, accion)


class AdscripcionOpcionesView(_Base):
    """GET /adscripcion/opciones?idPaciente=&turnoId= → consultorios elegibles."""

    def get(self, request):
        def accion():
            _operador(request, PERMISO_LEER)
            datos = _validar(request, OpcionesQuerySerializer, request.query_params)
            paciente = _paciente_o_404(datos["idPaciente"])
            evaluacion = evaluar_adscripcion(paciente)
            opciones = []
            if evaluacion.centro_sermed_id is not None:
                opciones = sugerir_consultorios(paciente, evaluacion.centro_sermed_id, turno_id=datos.get("turnoId"))
            return Response({
                "estado": evaluacion.estado,
                "idCentroSermed": evaluacion.centro_sermed_id,
                "opciones": [_opcion(o) for o in opciones],
            })
        return _responder(request, accion)


class AdscripcionPrevisualizarView(_Base):
    """POST /adscripcion/previsualizar → qué pasaría, sin escribir."""

    def post(self, request):
        def accion():
            _operador(request, PERMISO_LEER, escritura=True)
            datos = _validar(request, PrevisualizarSerializer, request.data)
            vista = previsualizar(id_paciente=datos["idPaciente"], consultorio_id=datos["consultorioId"])
            actual = vista.evaluacion.adscripcion
            return Response({
                "estado": vista.evaluacion.estado,
                "sinCambios": vista.sin_cambios,
                "idAdscripcionActual": actual.id if actual else None,
                "adscripcionActual": _adscripcion(actual),
                "citasACancelar": [_cita(c) for c in vista.citas_a_cancelar],
            })
        return _responder(request, accion)


class AdscripcionView(_Base):
    """POST /adscripcion → adscribir o reasignar."""

    def post(self, request):
        def accion():
            operador = _operador(request, PERMISO_ESCRIBIR, escritura=True)
            datos = _validar(request, AdscribirSerializer, request.data)
            resultado = adscribir(
                id_paciente=datos["idPaciente"],
                consultorio_id=datos["consultorioId"],
                id_adscripcion_esperada=datos["idAdscripcionEsperada"],
                citas_a_cancelar_ids=datos["citasACancelar"],
                motivo_cancelacion_id=datos.get("motivoCancelacionId"),
                origen=datos["origen"],
                fue_sugerida=datos["fueSugerida"],
                observaciones=datos.get("observaciones"),
                operador=operador,
                request=request,
            )
            pendientes = AdscripcionCitaAfectada.objects.select_related(
                "cita_cancelada__consultorio", "adscripcion__consultorio",
            ).filter(adscripcion=resultado.adscripcion, estatus=AdscripcionCitaAfectada.Estatus.PENDIENTE)
            return Response(
                {
                    "sinCambios": resultado.sin_cambios,
                    "adscripcion": _adscripcion(resultado.adscripcion),
                    "citasCanceladas": [_cita(c) for c in resultado.citas_canceladas],
                    "citasPorReagendar": [_cita_afectada(a) for a in pendientes],
                },
                status=status.HTTP_200_OK if resultado.sin_cambios else status.HTTP_201_CREATED,
            )
        return _responder(request, accion)


class AdscripcionHistorialView(_Base):
    """GET /adscripcion/pacientes/<id>/historial → activa y cerradas."""

    def get(self, request, id_paciente):
        def accion():
            _operador(request, PERMISO_LEER)
            items = (
                AdscripcionPaciente.objects.select_related("centro", "consultorio", "turno")
                .filter(paciente_id=id_paciente)
                .order_by("-fecha_inicio", "-id")
            )
            return Response({"items": [_adscripcion(a) for a in items]})
        return _responder(request, accion)


class CitasPorReagendarView(_Base):
    """GET /adscripcion/citas-por-reagendar?idPaciente=|centroId= → pendientes."""

    def get(self, request):
        def accion():
            operador = _operador(request, PERMISO_LEER)
            datos = _validar(request, CitasPorReagendarQuerySerializer, request.query_params)
            filtro = Q(estatus=AdscripcionCitaAfectada.Estatus.PENDIENTE)
            if datos.get("idPaciente"):
                filtro &= Q(adscripcion__paciente_id=datos["idPaciente"])
            if datos.get("centroId"):
                filtro &= Q(adscripcion__centro_id=datos["centroId"])
            if not datos.get("idPaciente") and not datos.get("centroId"):
                filtro &= Q(adscripcion__centro_id=operador.id_centro_atencion)
            items = (
                AdscripcionCitaAfectada.objects.select_related(
                    "cita_cancelada__consultorio", "adscripcion__consultorio",
                )
                .filter(filtro)
                .order_by("cita_cancelada__fecha_hora")
            )
            return Response({"items": [_cita_afectada(a) for a in items]})
        return _responder(request, accion)


class DescartarCitaAfectadaView(_Base):
    """POST /adscripcion/citas-por-reagendar/<id>/descartar."""

    def post(self, request, id_cita_afectada):
        def accion():
            operador = _operador(request, PERMISO_ESCRIBIR, escritura=True)
            datos = _validar(request, DescartarSerializer, request.data)
            afectada = descartar_cita_afectada(
                id_cita_afectada=id_cita_afectada, motivo=datos["motivo"], operador=operador, request=request,
            )
            return Response(_cita_afectada(afectada))
        return _responder(request, accion)


# ── Vistas de configuración ──────────────────────────────────────────────────

class EquivalenciasView(_Base):
    """GET/POST /adscripcion/config/clinicas."""

    def get(self, request):
        def accion():
            _operador(request, PERMISO_CONFIG)
            items = AdscripcionClinicaCentro.objects.select_related("centro").order_by("clave_clinica_sermed")
            return Response({"items": [_equivalencia(e) for e in items]})
        return _responder(request, accion)

    def post(self, request):
        def accion():
            operador = _operador(request, PERMISO_CONFIG, escritura=True)
            datos = _validar(request, EquivalenciaCrearSerializer, request.data)
            equivalencia = config_usecase.crear_equivalencia(
                clave_clinica_sermed=datos["claveClinicaSermed"], id_centro_atencion=datos["idCentroAtencion"],
                operador=operador, request=request,
            )
            return Response(_equivalencia(equivalencia), status=status.HTTP_201_CREATED)
        return _responder(request, accion)


class EquivalenciaDetalleView(_Base):
    """PATCH /adscripcion/config/clinicas/<id>."""

    def patch(self, request, id_clinica_centro):
        def accion():
            operador = _operador(request, PERMISO_CONFIG, escritura=True)
            datos = _validar(request, EquivalenciaCambiarSerializer, request.data)
            cambios = {}
            if "idCentroAtencion" in datos:
                cambios["id_centro_atencion"] = datos["idCentroAtencion"]
            if "estaActivo" in datos:
                cambios["esta_activo"] = datos["estaActivo"]
            equivalencia = config_usecase.actualizar_equivalencia(
                id_clinica_centro=id_clinica_centro, cambios=cambios, operador=operador, request=request,
            )
            return Response(_equivalencia(equivalencia))
        return _responder(request, accion)


class ConsultoriosFamiliaresView(_Base):
    """GET/POST /adscripcion/config/consultorios."""

    def get(self, request):
        def accion():
            _operador(request, PERMISO_CONFIG)
            datos = _validar(request, ConsultoriosQuerySerializer, request.query_params)
            items = AdscripcionConsultorio.objects.select_related("consultorio", "consultorio__id_turn")
            if datos.get("centroId"):
                items = items.filter(consultorio__id_center_id=datos["centroId"])
            cargas = dict(
                AdscripcionPaciente.objects.filter(estatus=AdscripcionPaciente.Estatus.ACTIVA)
                .values_list("consultorio_id")
                .annotate(total=Count("id"))
            )
            return Response({
                "items": [
                    _config_consultorio(c, cargas.get(c.consultorio_id, 0))
                    for c in items.order_by("consultorio__numero", "id")
                ],
            })
        return _responder(request, accion)

    def post(self, request):
        def accion():
            operador = _operador(request, PERMISO_CONFIG, escritura=True)
            datos = _validar(request, ConsultorioCrearSerializer, request.data)
            config = config_usecase.crear_consultorio_familiar(
                consultorio_id=datos["consultorioId"], capacidad_maxima=datos["capacidadMaxima"],
                operador=operador, request=request,
            )
            return Response(_config_consultorio(config, 0), status=status.HTTP_201_CREATED)
        return _responder(request, accion)


class ConsultorioFamiliarDetalleView(_Base):
    """PATCH /adscripcion/config/consultorios/<id>."""

    def patch(self, request, id_adscripcion_consultorio):
        def accion():
            operador = _operador(request, PERMISO_CONFIG, escritura=True)
            datos = _validar(request, ConsultorioCambiarSerializer, request.data)
            cambios = {}
            if "capacidadMaxima" in datos:
                cambios["capacidad_maxima"] = datos["capacidadMaxima"]
            if "estaActivo" in datos:
                cambios["esta_activo"] = datos["estaActivo"]
            config = config_usecase.actualizar_consultorio_familiar(
                id_adscripcion_consultorio=id_adscripcion_consultorio, cambios=cambios,
                operador=operador, request=request,
            )
            return Response(_config_consultorio(config))
        return _responder(request, accion)
