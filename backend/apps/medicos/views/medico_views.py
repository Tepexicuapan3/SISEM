"""
CRUD del catálogo de médicos.
Usa el mismo patrón de autorización que rbac_views.py.
"""

import logging
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from apps.authentication.services.response_service import error_response
from apps.administracion.views.rbac_views import (
    _apply_user_search_filter,
    _authorize,
    _request_id,
)
from apps.authentication.models import SyUsuario
from apps.medicos import identity
from apps.medicos.models import (
    CatMedico,
    RelMedicoEspecialidad,
    RelMedicoCentro,
    RelMedicoConsultorio,
    RelMedicoConsultorioHorario,
    RelMedicoExcepcion,
    RelMedicoCobertura,
    RelMedicoCoberturaHorario,
    CANAL_ATENCION,
)
from apps.medicos.disponibilidad import get_medicos_disponibles, get_disponibilidad_medico

CANALES_VALIDOS = {c[0] for c in CANAL_ATENCION}

logger = logging.getLogger(__name__)


# ─── HELPERS ────────────────────────────────────────────────────────────────

def resolve_medico(value, *, request=None, select_related=None, prefetch_related=None):
    """
    D7 (contrato dual, ventana de compatibilidad): resuelve el parámetro de
    ruta `/medicos/{value}/...` o un payload `medicoId`/`medicoSuplenteId`/
    `medicoTitularId` a un `CatMedico`. Intenta primero por la PK surrogate
    (`CatMedico.pk`); si no hay match, cae a `id_usuario` (comportamiento
    legacy previo al cambio medico-pk-independiente) y loguea el fallback
    -- el contador de ese WARN en logs es la métrica que habilita Fase 5
    (remover el fallback, ver design sección 5).
    """
    if value in (None, ""):
        return None

    qs = CatMedico.objects.all()
    if select_related:
        qs = qs.select_related(*select_related)
    if prefetch_related:
        qs = qs.prefetch_related(*prefetch_related)

    medico = qs.filter(pk=value).first()
    if medico is not None:
        return medico

    medico = qs.filter(id_usuario_id=value).first()
    if medico is not None:
        logger.warning(
            "MEDICO_ID_LEGACY_FALLBACK",
            extra={"value": value, "path": getattr(request, "path", None)},
        )
    return medico


def _serialize_medico(medico: CatMedico) -> dict:
    usuario = medico.id_usuario
    det = getattr(usuario, "detalle", None) if usuario is not None else None
    cedulas = list(usuario.cedulas.all().order_by("orden")) if usuario is not None else []
    especialidades = list(medico.especialidades.select_related("especialidad").all())
    centros = list(medico.centros.select_related("centro").filter(is_active=True))
    consultorios_activos = list(
        medico.consultorios.select_related("consultorio", "consultorio__id_center").filter(is_active=True)
    )

    escuela = getattr(det, "id_escuela", None) if det else None

    return {
        # "id" se mantiene como id_usuario (legacy) durante toda la ventana
        # de compatibilidad -- D7. "medicoId"/"usuarioId" son los campos
        # nuevos que reemplazan a "id" en Fase 5 (contract).
        "id": medico.id_usuario_id,
        "medicoId": medico.id,
        "usuarioId": medico.id_usuario_id,
        "username": usuario.usuario if usuario is not None else None,
        "nombreCompleto": identity.display_name(medico),
        "nombre": det.nombre if det else "",
        "paterno": det.paterno if det else "",
        "materno": det.materno if det else "",
        "email": usuario.correo if usuario is not None else None,
        "telefono": det.telefono if det else None,
        "direccion": det.direccion if det else None,
        "sexo": det.sexo if det else None,
        "fechaNac": str(det.fecha_nac) if det and det.fecha_nac else None,
        "isActive": usuario.est_activo if usuario is not None else False,
        "tipoMedico": medico.tipo_medico,
        "servicio": medico.servicio,
        "observaciones": medico.observaciones,
        "estatusMedico": medico.estatus_medico,
        "escuela": {"id": escuela.id, "code": escuela.code, "name": escuela.name} if escuela else None,
        "cedulas": [
            {"id": c.id, "numero": c.numero, "tipo": c.tipo, "esPrincipal": c.es_principal}
            for c in cedulas
        ],
        "especialidades": [
            {"id": e.especialidad_id, "name": e.especialidad.name, "esPrincipal": e.es_principal}
            for e in especialidades
        ],
        "centros": [
            {
                "id": c.id,
                "centroId": c.centro_id,
                "centroNombre": c.centro.name,
                "centroDireccion": getattr(c.centro, "address", None),
                "centroTelefono": getattr(c.centro, "phone", None),
                "tipoAdscripcion": c.tipo_adscripcion,
                "fechaInicio": str(c.fecha_inicio),
                "fechaFin": str(c.fecha_fin) if c.fecha_fin else None,
            }
            for c in centros
        ],
        "consultoriosActivos": [
            {
                "id": c.id,
                "consultorioId": c.consultorio_id,
                "consultorioNumero": c.consultorio.numero,
                "consultorioNombre": c.consultorio.name,
                "centroId": c.consultorio.id_center_id,
                "centroNombre": c.consultorio.id_center.name,
            }
            for c in consultorios_activos
        ],
        "createdAt": medico.created_at.isoformat() if medico.created_at else None,
    }


def _serialize_consultorio_asignacion(rmc: RelMedicoConsultorio) -> dict:
    return {
        "id": rmc.id,
        "consultorioId": rmc.consultorio_id,
        "consultorioNumero": rmc.consultorio.numero,
        "consultorioNombre": rmc.consultorio.name,
        "tipoAsignacion": rmc.tipo_asignacion,
        "fechaInicio": str(rmc.fecha_inicio),
        "fechaFin": str(rmc.fecha_fin) if rmc.fecha_fin else None,
        "isActive": rmc.is_active,
        "horarios": [
            {
                "id": h.id,
                "diaSemana": h.dia_semana,
                "horaInicio": str(h.hora_inicio),
                "horaFin": str(h.hora_fin),
                "intervaloCitaMin": h.intervalo_cita_min,
                "canal": h.canal,
            }
            for h in rmc.horarios.all().order_by("dia_semana", "hora_inicio")
        ],
    }


def _validar_canal_horarios(horarios: list) -> str | None:
    """Valida que el canal de cada horario (si viene) sea uno de los choices válidos.
    Retorna el mensaje de error si alguno es inválido, o None si todos son válidos."""
    for h in horarios:
        canal = h.get("canal")
        if canal is not None and canal not in CANALES_VALIDOS:
            return (
                f"canal inválido: '{canal}'. Valores permitidos: "
                f"{', '.join(sorted(CANALES_VALIDOS))}."
            )
    return None


# ─── CRUD MÉDICOS ────────────────────────────────────────────────────────────

class MedicosListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, auth_error = _authorize(request, "admin:gestion:medicos:read")
        if auth_error:
            return auth_error

        qs = CatMedico.objects.select_related(
            "id_usuario", "id_usuario__detalle", "id_usuario__detalle__id_escuela"
        ).prefetch_related(
            "id_usuario__cedulas",
            "especialidades__especialidad",
            "centros__centro",
            "consultorios__consultorio__id_center",
        )

        tipo = request.query_params.get("tipoMedico")
        if tipo:
            qs = qs.filter(tipo_medico=tipo)

        estatus = request.query_params.get("estatusMedico")
        if estatus:
            qs = qs.filter(estatus_medico=estatus)

        search = request.query_params.get("search")
        qs = _apply_user_search_filter(
            qs, search, path_prefix="id_usuario__", include_correo=False
        )

        items = [_serialize_medico(m) for m in qs.order_by("id_usuario__detalle__nombre_completo")]
        return Response({"items": items, "total": len(items)})

    @transaction.atomic
    def post(self, request):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:create", require_csrf=True)
        if auth_error:
            return auth_error

        usuario_id = request.data.get("usuarioId")

        if not usuario_id:
            # D8/F4-27: alta de médico SIN usuario queda detrás del feature
            # flag -- mientras "id" siga siendo id_usuario_id (D7), un
            # médico sin usuario serializaría "id": null y rompería el
            # frontend legacy. Se habilita recién en Fase 5 (contract).
            if not getattr(settings, "MEDICOS_ALLOW_SIN_USUARIO", False):
                return error_response("VALIDATION_ERROR", "usuarioId es requerido.",
                                      status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

            nombre_display = request.data.get("nombreDisplay") or None
            if not nombre_display:
                return error_response(
                    "VALIDATION_ERROR", "nombreDisplay es requerido cuando no se envía usuarioId.",
                    status.HTTP_400_BAD_REQUEST, request_id=_request_id(request),
                )

            medico = CatMedico.objects.create(
                id_usuario=None,
                nombre_display=nombre_display,
                tipo_medico=request.data.get("tipoMedico", "CLINICA"),
                servicio=request.data.get("servicio") or None,
                observaciones=request.data.get("observaciones") or None,
                created_by_id=actor.id_usuario,
            )
            return Response(_serialize_medico(medico), status=status.HTTP_201_CREATED)

        usuario = SyUsuario.objects.select_related("detalle").filter(id_usuario=usuario_id).first()
        if not usuario:
            return error_response("USER_NOT_FOUND", "Usuario no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        det = getattr(usuario, "detalle", None)
        if not det or not det.id_tipo_personal or det.id_tipo_personal.name != "Médico":
            return error_response(
                "TIPO_PERSONAL_INVALIDO",
                "El usuario debe tener tipo_personal = MEDICO.",
                status.HTTP_400_BAD_REQUEST,
                request_id=_request_id(request),
            )

        if CatMedico.objects.filter(id_usuario=usuario).exists():
            return error_response("MEDICO_EXISTS", "Este usuario ya tiene un perfil de médico.",
                                  status.HTTP_409_CONFLICT, request_id=_request_id(request))

        medico = CatMedico.objects.create(
            id_usuario=usuario,
            tipo_medico=request.data.get("tipoMedico", "CLINICA"),
            servicio=request.data.get("servicio") or None,
            observaciones=request.data.get("observaciones") or None,
            created_by_id=actor.id_usuario,
        )
        return Response(_serialize_medico(medico), status=status.HTTP_201_CREATED)


class MedicoDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def _get_medico(self, user_id, request=None):
        return resolve_medico(
            user_id,
            request=request,
            select_related=["id_usuario", "id_usuario__detalle", "id_usuario__detalle__id_escuela"],
            prefetch_related=[
                "id_usuario__cedulas",
                "especialidades__especialidad",
                "centros__centro",
                "consultorios__consultorio__id_center",
            ],
        )

    def get(self, request, user_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:read")
        if auth_error:
            return auth_error

        medico = self._get_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        data = _serialize_medico(medico)

        # Incluir solo consultorios activos con sus horarios
        consultorios = RelMedicoConsultorio.objects.select_related(
            "consultorio"
        ).prefetch_related("horarios").filter(medico=medico, is_active=True)
        data["consultorios"] = [_serialize_consultorio_asignacion(c) for c in consultorios]

        return Response({"medico": data})

    @transaction.atomic
    def patch(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        medico = self._get_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        if "tipoMedico" in request.data:
            medico.tipo_medico = request.data["tipoMedico"]
        if "servicio" in request.data:
            medico.servicio = request.data.get("servicio") or None
        if "observaciones" in request.data:
            medico.observaciones = request.data.get("observaciones") or None
        if "estatusMedico" in request.data:
            medico.estatus_medico = request.data["estatusMedico"]

        medico.updated_at = timezone.now()
        medico.updated_by_id = actor.id_usuario
        medico.save()
        return Response(_serialize_medico(medico))


# ─── ESPECIALIDADES ──────────────────────────────────────────────────────────

class MedicoEspecialidadesView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        esp_id = request.data.get("especialidadId")
        if not esp_id:
            return error_response("VALIDATION_ERROR", "especialidadId requerido.",
                                  status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

        from apps.catalogos.models import Especialidades
        esp = Especialidades.objects.filter(id=esp_id).first()
        if not esp:
            return error_response("ESPECIALIDAD_NOT_FOUND", "Especialidad no encontrada.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        es_principal = bool(request.data.get("esPrincipal", False))
        if es_principal:
            RelMedicoEspecialidad.objects.filter(medico=medico, es_principal=True).update(es_principal=False)

        rel, created = RelMedicoEspecialidad.objects.get_or_create(
            medico=medico, especialidad=esp,
            defaults={"es_principal": es_principal},
        )
        if not created:
            rel.es_principal = es_principal
            rel.save()

        return Response({"id": rel.id, "especialidadId": esp.id, "name": esp.name, "esPrincipal": rel.es_principal},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, user_id, especialidad_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        RelMedicoEspecialidad.objects.filter(
            medico_id=medico.id, especialidad_id=especialidad_id
        ).delete()
        return Response({"success": True})


# ─── CENTROS ─────────────────────────────────────────────────────────────────

class MedicoCentrosView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        from apps.catalogos.models import CatCentroAtencion
        centro = CatCentroAtencion.objects.filter(id=request.data.get("centroId")).first()
        if not centro:
            return error_response("CENTRO_NOT_FOUND", "Centro no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        rel = RelMedicoCentro.objects.create(
            medico=medico,
            centro=centro,
            tipo_adscripcion=request.data.get("tipoAdscripcion", "DEFINITIVA"),
            fecha_inicio=request.data.get("fechaInicio", date.today()),
            fecha_fin=request.data.get("fechaFin") or None,
            created_by_id=actor.id_usuario,
        )
        return Response({
            "id": rel.id, "centroId": rel.centro_id, "centroNombre": centro.name,
            "tipoAdscripcion": rel.tipo_adscripcion,
            "fechaInicio": str(rel.fecha_inicio), "fechaFin": str(rel.fecha_fin) if rel.fecha_fin else None,
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, user_id, rel_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:update", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        RelMedicoCentro.objects.filter(id=rel_id, medico_id=medico.id).update(
            is_active=False, fecha_fin=date.today()
        )
        return Response({"success": True})


# ─── CONSULTORIOS Y HORARIOS ─────────────────────────────────────────────────

class MedicoConsultoriosView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, user_id, rmc_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        rmc = RelMedicoConsultorio.objects.select_related("consultorio").filter(
            id=rmc_id, medico_id=getattr(medico, "id", None)
        ).first()
        if not rmc:
            return error_response("NOT_FOUND", "Asignación no encontrada.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        if "consultorioId" in request.data:
            from apps.catalogos.models import Consultorios
            consultorio = Consultorios.objects.filter(id=request.data["consultorioId"]).first()
            if not consultorio:
                return error_response("CONSULTORIO_NOT_FOUND", "Consultorio no encontrado.",
                                      status.HTTP_404_NOT_FOUND, request_id=_request_id(request))
            rmc.consultorio = consultorio

        if "tipoAsignacion" in request.data:
            rmc.tipo_asignacion = request.data["tipoAsignacion"]

        rmc.save()
        return Response(_serialize_consultorio_asignacion(
            RelMedicoConsultorio.objects.prefetch_related("horarios").get(id=rmc.id)
        ))

    def delete(self, request, user_id, rmc_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        RelMedicoConsultorio.objects.filter(id=rmc_id, medico_id=getattr(medico, "id", None)).update(
            is_active=False, fecha_fin=date.today()
        )
        return Response({"success": True})

    @transaction.atomic
    def post(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        from apps.catalogos.models import Consultorios
        consultorio = Consultorios.objects.filter(id=request.data.get("consultorioId")).first()
        if not consultorio:
            return error_response("CONSULTORIO_NOT_FOUND", "Consultorio no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        horarios_payload = request.data.get("horarios", [])
        error_canal = _validar_canal_horarios(horarios_payload)
        if error_canal:
            return error_response("VALIDATION_ERROR", error_canal,
                                  status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

        rmc = RelMedicoConsultorio.objects.create(
            medico=medico,
            consultorio=consultorio,
            tipo_asignacion=request.data.get("tipoAsignacion", "PERMANENTE"),
            fecha_inicio=request.data.get("fechaInicio", date.today()),
            fecha_fin=request.data.get("fechaFin") or None,
            created_by_id=actor.id_usuario,
        )

        # Crear horarios si vienen en el payload
        for h in horarios_payload:
            RelMedicoConsultorioHorario.objects.create(
                rel_medico_consultorio=rmc,
                dia_semana=h["diaSemana"],
                hora_inicio=h["horaInicio"],
                hora_fin=h["horaFin"],
                intervalo_cita_min=h.get("intervaloCitaMin", 20),
                canal=h.get("canal", "PRESENCIAL"),
            )

        return Response(_serialize_consultorio_asignacion(
            RelMedicoConsultorio.objects.prefetch_related("horarios").get(id=rmc.id)
        ), status=status.HTTP_201_CREATED)


class MedicoConsultorioHorarioView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def put(self, request, user_id, rmc_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:horarios", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        rmc = RelMedicoConsultorio.objects.filter(id=rmc_id, medico_id=getattr(medico, "id", None)).first()
        if not rmc:
            return error_response("NOT_FOUND", "Asignación no encontrada.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        horarios_payload = request.data.get("horarios", [])
        error_canal = _validar_canal_horarios(horarios_payload)
        if error_canal:
            return error_response("VALIDATION_ERROR", error_canal,
                                  status.HTTP_400_BAD_REQUEST, request_id=_request_id(request))

        # Reemplaza todos los horarios de esta asignación
        rmc.horarios.all().delete()
        for h in horarios_payload:
            RelMedicoConsultorioHorario.objects.create(
                rel_medico_consultorio=rmc,
                dia_semana=h["diaSemana"],
                hora_inicio=h["horaInicio"],
                hora_fin=h["horaFin"],
                intervalo_cita_min=h.get("intervaloCitaMin", 20),
                canal=h.get("canal", "PRESENCIAL"),
            )

        # Regenerar slots: elimina futuros disponibles y vuelve a generar
        # desde el nuevo horario. Los slots con cita asignada se preservan.
        from datetime import date as _date
        from apps.recepcion.models import HorarioDisponible
        from apps.recepcion.repositories.citas_repository import CitasRepository
        HorarioDisponible.objects.filter(
            medico_id=rmc.medico_id,
            fecha__gte=_date.today(),
            disponible=True,
            cita__isnull=True,
        ).delete()
        CitasRepository.generar_slots_medico(medico_id=rmc.medico_id, dias_adelante=60)

        return Response(_serialize_consultorio_asignacion(
            RelMedicoConsultorio.objects.prefetch_related("horarios").get(id=rmc.id)
        ))


# ─── EXCEPCIONES ─────────────────────────────────────────────────────────────

class MedicoExcepcionesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, user_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:read")
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        excepciones = RelMedicoExcepcion.objects.filter(
            medico_id=getattr(medico, "id", None), is_active=True
        ).order_by("fecha_inicio")

        return Response({"items": [
            {
                "id": e.id, "tipo": e.tipo,
                "fechaInicio": str(e.fecha_inicio), "fechaFin": str(e.fecha_fin),
                "horaInicio": str(e.hora_inicio) if e.hora_inicio else None,
                "horaFin": str(e.hora_fin) if e.hora_fin else None,
                "motivo": e.motivo, "consultorioId": e.consultorio_id,
            }
            for e in excepciones
        ]})

    @transaction.atomic
    def post(self, request, user_id):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:excepciones", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        exc = RelMedicoExcepcion.objects.create(
            medico=medico,
            tipo=request.data.get("tipo"),
            fecha_inicio=request.data.get("fechaInicio"),
            fecha_fin=request.data.get("fechaFin"),
            hora_inicio=request.data.get("horaInicio") or None,
            hora_fin=request.data.get("horaFin") or None,
            consultorio_id=request.data.get("consultorioId") or None,
            motivo=request.data.get("motivo") or None,
            created_by_id=actor.id_usuario,
        )

        # Actualizar estatus si es una excepción de baja/vacaciones de larga duración
        if exc.tipo in ("VACACIONES", "INCAPACIDAD", "SUSPENSION"):
            medico.estatus_medico = exc.tipo if exc.tipo != "VACACIONES" else "VACACIONES"
            medico.updated_at = timezone.now()
            medico.save(update_fields=["estatus_medico", "updated_at"])

        return Response({"id": exc.id, "tipo": exc.tipo,
                         "fechaInicio": str(exc.fecha_inicio), "fechaFin": str(exc.fecha_fin)},
                        status=status.HTTP_201_CREATED)

    def delete(self, request, user_id, exc_id):
        _, auth_error = _authorize(request, "admin:gestion:medicos:excepciones", require_csrf=True)
        if auth_error:
            return auth_error

        medico = resolve_medico(user_id, request=request)
        RelMedicoExcepcion.objects.filter(id=exc_id, medico_id=getattr(medico, "id", None)).update(is_active=False)
        return Response({"success": True})


# ─── COBERTURAS ──────────────────────────────────────────────────────────────

class MedicoCoberturasView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):
        actor, auth_error = _authorize(request, "admin:gestion:medicos:coberturas", require_csrf=True)
        if auth_error:
            return auth_error

        suplente = resolve_medico(request.data.get("medicoSuplenteId"), request=request)
        titular  = resolve_medico(request.data.get("medicoTitularId"), request=request)
        if not suplente or not titular:
            return error_response("MEDICO_NOT_FOUND", "Médico suplente o titular no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        from apps.catalogos.models import Consultorios, CatCentroAtencion
        cob = RelMedicoCobertura.objects.create(
            medico_suplente=suplente,
            medico_titular=titular,
            consultorio_id=request.data.get("consultorioId"),
            centro_id=request.data.get("centroId"),
            fecha_inicio=request.data.get("fechaInicio"),
            fecha_fin=request.data.get("fechaFin"),
            motivo=request.data.get("motivo", "OTRO"),
            created_by_id=actor.id_usuario,
        )

        for h in request.data.get("horarios", []):
            RelMedicoCoberturaHorario.objects.create(
                cobertura=cob,
                dia_semana=h["diaSemana"],
                hora_inicio=h["horaInicio"],
                hora_fin=h["horaFin"],
            )

        return Response({"id": cob.id, "medicoSuplenteId": cob.medico_suplente_id,
                         "medicoTitularId": cob.medico_titular_id,
                         "fechaInicio": str(cob.fecha_inicio), "fechaFin": str(cob.fecha_fin)},
                        status=status.HTTP_201_CREATED)


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

        medico = resolve_medico(user_id, request=request, select_related=["id_usuario"])
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
        medico = resolve_medico(user_id, request=request)
        if not medico:
            return error_response("MEDICO_NOT_FOUND", "Médico no encontrado.",
                                  status.HTTP_404_NOT_FOUND, request_id=_request_id(request))

        dias = int(request.data.get("diasAdelante", 30))
        dias = max(1, min(dias, 90))  # entre 1 y 90 días

        creados = CitasRepository.generar_slots_medico(medico_id=medico.id, dias_adelante=dias)
        return Response({"medicoId": medico.id, "slotsCreados": creados, "diasAdelante": dias})
