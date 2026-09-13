"""
CRUD del catálogo de médicos. Vistas de transporte puro: autorizan,
delegan a `uses_case/` y formatean la respuesta con `presenters.py`. Toda
la lógica de negocio y acceso a datos vive en `uses_case/`/`repositories/`
(ver AGENTS.md / backend/apps/README.md — "logica critica en use_cases,
nunca en transport").
"""

from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from apps.authentication.services.response_service import error_response
from apps.administracion.views.rbac_views import _authorize, _request_id
from apps.recepcion.services.errors import VisitDomainError

from apps.medicos import presenters
from apps.medicos.disponibilidad import get_medicos_disponibles, get_disponibilidad_medico
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.medicos.uses_case import (
    centro_usecase,
    cobertura_usecase,
    consultorio_usecase,
    especialidad_usecase,
    excepcion_usecase,
    medico_usecase,
)


def _domain_error_response(request, exc: VisitDomainError):
    return error_response(
        exc.code, exc.message, exc.status_code,
        details=exc.details, request_id=_request_id(request),
    )


# ─── CRUD MÉDICOS ────────────────────────────────────────────────────────────

class MedicosListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, auth_error = _authorize(request, "admin:gestion:medicos:read")
        if auth_error:
            return auth_error

        medicos = medico_usecase.list_medicos(
            tipo_medico=request.query_params.get("tipoMedico"),
            estatus_medico=request.query_params.get("estatusMedico"),
            search=request.query_params.get("search"),
        )
        items = [presenters.serialize_medico(m) for m in medicos]
        return Response({"items": items, "total": len(items)})

    def post(self, request):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:create", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            medico = medico_usecase.create_medico(request.data, actor_id=actor.id_usuario)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(presenters.serialize_medico(medico), status=status.HTTP_201_CREATED)


class MedicoDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, user_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:read")
        if auth_error:
            return auth_error

        try:
            medico, consultorios = medico_usecase.get_medico_detail(user_id, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        data = presenters.serialize_medico(medico)
        data["consultorios"] = [presenters.serialize_consultorio_asignacion(c) for c in consultorios]

        return Response({"medico": data})

    def patch(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            medico = medico_usecase.get_medico_or_404(user_id, request=request)
            medico = medico_usecase.update_medico(medico, request.data, actor_id=actor.id_usuario)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(presenters.serialize_medico(medico))


# ─── ESPECIALIDADES ──────────────────────────────────────────────────────────

class MedicoEspecialidadesView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, user_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            rel, created = especialidad_usecase.add_especialidad(user_id, request.data, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(
            presenters.serialize_especialidad(rel),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, user_id, especialidad_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            especialidad_usecase.remove_especialidad(user_id, especialidad_id, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response({"success": True})


# ─── CENTROS ─────────────────────────────────────────────────────────────────

class MedicoCentrosView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            rel = centro_usecase.add_centro(user_id, request.data, actor_id=actor.id_usuario, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(presenters.serialize_centro(rel), status=status.HTTP_201_CREATED)

    def delete(self, request, user_id, rel_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            centro_usecase.remove_centro(user_id, rel_id, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response({"success": True})


# ─── CONSULTORIOS Y HORARIOS ─────────────────────────────────────────────────

class MedicoConsultoriosView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            rmc = consultorio_usecase.add_consultorio(
                user_id, request.data, actor_id=actor.id_usuario, request=request,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(presenters.serialize_consultorio_asignacion(rmc), status=status.HTTP_201_CREATED)

    def patch(self, request, user_id, rmc_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            rmc = consultorio_usecase.update_consultorio_asignacion(
                user_id, rmc_id, request.data, request=request,
            )
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(presenters.serialize_consultorio_asignacion(rmc))

    def delete(self, request, user_id, rmc_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        consultorio_usecase.remove_consultorio(user_id, rmc_id, request=request)
        return Response({"success": True})


class MedicoConsultorioHorarioView(APIView):
    authentication_classes = []
    permission_classes = []

    def put(self, request, user_id, rmc_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            rmc = consultorio_usecase.save_horario(user_id, rmc_id, request.data, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(presenters.serialize_consultorio_asignacion(rmc))


# ─── EXCEPCIONES ─────────────────────────────────────────────────────────────

class MedicoExcepcionesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, user_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:read")
        if auth_error:
            return auth_error

        excepciones = excepcion_usecase.list_excepciones(user_id, request=request)
        return Response({"items": [presenters.serialize_excepcion(e) for e in excepciones]})

    def post(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:excepciones", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            exc = excepcion_usecase.create_excepcion(
                user_id, request.data, actor_id=actor.id_usuario, request=request,
            )
        except VisitDomainError as exc_error:
            return _domain_error_response(request, exc_error)

        return Response(presenters.serialize_excepcion_created(exc), status=status.HTTP_201_CREATED)

    def delete(self, request, user_id, exc_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:excepciones", require_csrf=True)
        if auth_error:
            return auth_error

        excepcion_usecase.delete_excepcion(user_id, exc_id, request=request)
        return Response({"success": True})


# ─── COBERTURAS ──────────────────────────────────────────────────────────────

class MedicoCoberturasView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        GET /coberturas?medicoId=<id> — coberturas donde el médico participa
        como suplente o como titular (ambos roles). `medicoId` es obligatorio:
        sin él el listado no tiene alcance definido para ningún caso de uso
        real (siempre se consulta desde el detalle de un médico).
        """
        _, auth_error = _authorize(request, "admin:gestion:medicos:read")
        if auth_error:
            return auth_error

        medico_id = request.query_params.get("medicoId")
        if not medico_id:
            return error_response("VALIDATION_ERROR", "medicoId requerido.",
                                  status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

        try:
            coberturas = cobertura_usecase.list_coberturas(medico_id, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response({"items": [presenters.serialize_cobertura(c) for c in coberturas]})

    def post(self, request):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:coberturas", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            cob = cobertura_usecase.create_cobertura(request.data, actor_id=actor.id_usuario, request=request)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response(presenters.serialize_cobertura(cob), status=status.HTTP_201_CREATED)


class MedicoCoberturaDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def delete(self, request, cobertura_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:coberturas", require_csrf=True)
        if auth_error:
            return auth_error

        try:
            cobertura_usecase.delete_cobertura(cobertura_id)
        except VisitDomainError as exc:
            return _domain_error_response(request, exc)

        return Response({"success": True})


# ─── DISPONIBILIDAD ──────────────────────────────────────────────────────────

class MedicosDisponiblesView(APIView):
    """Consultada por recepción y módulo de citas."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, auth_error = _authorize(request, "recepcion:read")
        if auth_error:
            return auth_error

        centro_id = request.query_params.get("centroId")
        fecha_str = request.query_params.get("fecha")

        if not centro_id:
            return error_response("VALIDATION_ERROR", "centroId requerido.",
                                  status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

        try:
            fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()
        except ValueError:
            return error_response("VALIDATION_ERROR", "fecha inválida (YYYY-MM-DD).",
                                  status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

        medicos = get_medicos_disponibles(int(centro_id), fecha)
        return Response({"fecha": str(fecha), "centroId": int(centro_id), "medicos": medicos})


class MedicoDisponibilidadView(APIView):
    """Disponibilidad de un médico específico en una fecha."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, user_id):
        _, auth_error = _authorize(request, "recepcion:read")
        if auth_error:
            return auth_error

        medico = MedicoRepository.resolve(user_id, request=request, select_related=["id_usuario"])
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        fecha_str = request.query_params.get("fecha")
        try:
            fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()
        except ValueError:
            return error_response("VALIDATION_ERROR", "fecha inválida.",
                                  status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

        disp = get_disponibilidad_medico(medico, fecha)
        return Response({
            "medicoId": medico.id, "usuarioId": medico.id_usuario_id,
            "fecha": str(fecha), **disp,
        })


class GenerarSlotsView(APIView):
    """POST /medicos/{user_id}/slots/generar — genera HorarioDisponible para los próximos N días."""

    authentication_classes = []
    permission_classes     = []

    def post(self, request, user_id):
        _, auth_error = _authorize(request, "recepcion:read")
        if auth_error:
            return auth_error

        from apps.recepcion.repositories.citas_repository import CitasRepository

        # generar_slots_medico filtra/crea HorarioDisponible.medico_id
        # (espacio médico) -- se resuelve el {user_id} de la ruta a
        # CatMedico.pk (D7) en vez de pasarlo directo (R1).
        medico = MedicoRepository.resolve(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        dias = int(request.data.get("diasAdelante", 30))
        dias = max(1, min(dias, 90))  # entre 1 y 90 días

        creados = CitasRepository.generar_slots_medico(medico_id=medico.id, dias_adelante=dias)
        return Response({"medicoId": medico.id, "slotsCreados": creados, "diasAdelante": dias})
