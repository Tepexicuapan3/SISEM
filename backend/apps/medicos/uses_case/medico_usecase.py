from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.medicos.identity import annotate_display_name
from apps.medicos.repositories.consultorio_repository import ConsultorioRepository
from apps.medicos.repositories.medico_repository import LegacyMedicoRepository, MedicoRepository
from apps.recepcion.services.errors import VisitDomainError


def list_medicos(*, tipo_medico=None, estatus_medico=None, search=None):
    qs = MedicoRepository.list_queryset()

    if tipo_medico:
        qs = qs.filter(tipo_medico=tipo_medico)
    if estatus_medico:
        qs = qs.filter(estatus_medico=estatus_medico)

    # Búsqueda multi-palabra: cada token debe coincidir en usuario, nombre
    # completo del DetUsuario o, si es dígito, en el No. Médico (id).
    for token in (search or "").split():
        cond = (
            Q(id_usuario__usuario__icontains=token)
            | Q(id_usuario__detalle__nombre_completo__icontains=token)
        )
        if token.isdigit():
            cond |= Q(id=int(token))
        qs = qs.filter(cond)

    # Orden por nombre a mostrar (del usuario); `id` desempata.
    return annotate_display_name(qs).order_by("medico_nombre", "id")


LEGACY_MAX_PAGE_SIZE = 100


def list_legacy_medicos(*, search=None, status=None, page=1, page_size=20):
    """
    Archivo legado de médicos (solo lectura), paginado.

    Un código legado (`no_medico`, `cd_medico`) solo sirve para buscar en
    `legacy_medico`; jamás se resuelve como `CatMedico.id`.
    """
    qs = LegacyMedicoRepository.list_queryset()

    if status:
        qs = qs.filter(sw_status=status)

    for token in (search or "").split():
        cond = (
            Q(ds_nombre__icontains=token)
            | Q(ds_paterno__icontains=token)
            | Q(ds_materno__icontains=token)
            | Q(cd_medico__icontains=token)
            | Q(no_cedula__icontains=token)
        )
        if token.isdigit():
            cond |= Q(no_medico=int(token))
        qs = qs.filter(cond)

    qs = qs.order_by("ds_paterno", "ds_materno", "ds_nombre", "no_medico")

    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), LEGACY_MAX_PAGE_SIZE)
    total = qs.count()
    rows = list(qs[(page - 1) * page_size: page * page_size])
    return {
        "rows": rows,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": max((total + page_size - 1) // page_size, 1),
    }


@transaction.atomic
def create_medico(data, *, actor_id):
    usuario_id = data.get("usuarioId")

    if not usuario_id:
        # El alta exige un usuario existente con tipo_personal Médico: ningún
        # camino crea un médico sin usuario.
        raise VisitDomainError("VALIDATION_ERROR", "usuarioId es requerido.", 400)

    usuario = MedicoRepository.get_usuario_candidato(usuario_id)
    if not usuario:
        raise VisitDomainError("USER_NOT_FOUND", "Usuario no encontrado.", 404)

    if not MedicoRepository.usuario_es_medico(usuario):
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


def get_medico_or_404(medico_id, *, request=None):
    medico = MedicoRepository.resolve_with_detail(medico_id, request=request)
    if not medico:
        raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)
    return medico


def get_medico_detail(medico_id, *, request=None):
    """Médico + solo sus consultorios activos con horarios (para el detalle;
    el listado general solo expone `consultoriosActivos` resumido, sin
    horarios -- ver presenters.serialize_medico)."""
    medico = get_medico_or_404(medico_id, request=request)
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
    estatus_anterior = medico.estatus_medico
    if "estatusMedico" in data:
        medico.estatus_medico = data["estatusMedico"]

    medico.updated_at = timezone.now()
    medico.updated_by_id = actor_id
    MedicoRepository.save(medico)

    # La generación semanal salta a los médicos no ACTIVOS: al reactivarlo
    # se generan sus horarios sin esperar al lunes. (Mientras no está ACTIVO,
    # sus horarios no se listan ni se reservan.)
    if estatus_anterior != "ACTIVO" and medico.estatus_medico == "ACTIVO":
        from apps.recepcion.repositories.citas_repository import CitasRepository

        CitasRepository.generar_slots_medico(medico_id=medico.id, dias_adelante=30)
    return medico
