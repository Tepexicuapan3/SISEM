from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.administracion.views.rbac_views import _apply_user_search_filter
from apps.medicos.repositories.consultorio_repository import ConsultorioRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.recepcion.services.errors import VisitDomainError


def list_medicos(*, tipo_medico=None, estatus_medico=None, search=None):
    qs = MedicoRepository.list_queryset()

    if tipo_medico:
        qs = qs.filter(tipo_medico=tipo_medico)
    if estatus_medico:
        qs = qs.filter(estatus_medico=estatus_medico)

    qs = _apply_user_search_filter(qs, search, path_prefix="id_usuario__", include_correo=False)

    return qs.order_by("id_usuario__detalle__nombre_completo")


@transaction.atomic
def create_medico(data, *, actor_id):
    usuario_id = data.get("usuarioId")

    if not usuario_id:
        # D8/F4-27: alta de médico SIN usuario queda detrás del feature
        # flag -- mientras "id" siga siendo id_usuario_id (D7), un médico
        # sin usuario serializaría "id": null y rompería el frontend legacy.
        # Se habilita recién en Fase 5 (contract).
        if not getattr(settings, "MEDICOS_ALLOW_SIN_USUARIO", False):
            raise VisitDomainError("VALIDATION_ERROR", "usuarioId es requerido.", 400)

        nombre_display = data.get("nombreDisplay") or None
        if not nombre_display:
            raise VisitDomainError(
                "VALIDATION_ERROR",
                "nombreDisplay es requerido cuando no se envía usuarioId.",
                400,
            )

        return MedicoRepository.create(
            usuario=None,
            nombre_display=nombre_display,
            tipo_medico=data.get("tipoMedico", "CLINICA"),
            servicio=data.get("servicio") or None,
            observaciones=data.get("observaciones") or None,
            created_by_id=actor_id,
        )

    usuario = MedicoRepository.get_usuario_candidato(usuario_id)
    if not usuario:
        raise VisitDomainError("USER_NOT_FOUND", "Usuario no encontrado.", 404)

    det = getattr(usuario, "detalle", None)
    if not det or not det.id_tipo_personal or det.id_tipo_personal.name != "Médico":
        raise VisitDomainError(
            "TIPO_PERSONAL_INVALIDO", "El usuario debe tener tipo_personal = MEDICO.", 400,
        )

    if MedicoRepository.exists_for_usuario(usuario):
        raise VisitDomainError(
            "MEDICO_EXISTS", "Este usuario ya tiene un perfil de médico.", 409,
        )

    return MedicoRepository.create(
        usuario=usuario,
        tipo_medico=data.get("tipoMedico", "CLINICA"),
        servicio=data.get("servicio") or None,
        observaciones=data.get("observaciones") or None,
        created_by_id=actor_id,
    )


def get_medico_or_404(user_id, *, request=None):
    medico = MedicoRepository.resolve_with_detail(user_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)
    return medico


def get_medico_detail(user_id, *, request=None):
    """Médico + solo sus consultorios activos con horarios (para el detalle;
    el listado general solo expone `consultoriosActivos` resumido, sin
    horarios -- ver presenters.serialize_medico)."""
    medico = get_medico_or_404(user_id, request=request)
    consultorios = ConsultorioRepository.list_active_for_medico(medico)
    return medico, consultorios


@transaction.atomic
def update_medico(medico, data, *, actor_id):
    if "tipoMedico" in data:
        medico.tipo_medico = data["tipoMedico"]
    if "servicio" in data:
        medico.servicio = data.get("servicio") or None
    if "observaciones" in data:
        medico.observaciones = data.get("observaciones") or None
    if "estatusMedico" in data:
        medico.estatus_medico = data["estatusMedico"]

    medico.updated_at = timezone.now()
    medico.updated_by_id = actor_id
    MedicoRepository.save(medico)
    return medico
