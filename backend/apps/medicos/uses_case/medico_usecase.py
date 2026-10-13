from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.authentication.models import DetUsuario, DetUsuarioCedula
from apps.medicos.identity import annotate_display_name, invalidate_identity_cache
from apps.medicos.models import CatMedico
from apps.medicos.repositories.consultorio_repository import ConsultorioRepository
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.recepcion.services.errors import VisitDomainError


def list_medicos(*, tipo_medico=None, estatus_medico=None, search=None):
    qs = MedicoRepository.list_queryset()

    if tipo_medico:
        qs = qs.filter(tipo_medico=tipo_medico)
    if estatus_medico:
        qs = qs.filter(estatus_medico=estatus_medico)

    # Búsqueda multi-palabra: cada token debe coincidir en usuario, nombre
    # completo del DetUsuario, nombre/paterno/materno propios (médicos sin
    # usuario) o, si es dígito, en el No. Médico (id). Los OR sobre joins
    # NULLables son LEFT JOIN, así que los médicos sin usuario no se pierden.
    for token in (search or "").split():
        cond = (
            Q(id_usuario__usuario__icontains=token)
            | Q(id_usuario__detalle__nombre_completo__icontains=token)
            | Q(nombre__icontains=token)
            | Q(paterno__icontains=token)
            | Q(materno__icontains=token)
        )
        if token.isdigit():
            cond |= Q(id=int(token))
        qs = qs.filter(cond)

    # Orden por nombre a mostrar (usuario o campos propios); `id` desempata.
    return annotate_display_name(qs).order_by("medico_nombre", "id")


@transaction.atomic
def create_medico(data, *, actor_id):
    usuario_id = data.get("usuarioId")

    if not usuario_id:
        # El alta manual exige un usuario existente con tipo_personal Médico.
        # Los médicos sin usuario entran SOLO por el import Excel.
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
    if "estatusMedico" in data:
        medico.estatus_medico = data["estatusMedico"]

    medico.updated_at = timezone.now()
    medico.updated_by_id = actor_id
    MedicoRepository.save(medico)
    return medico


def assign_usuario(medico_id, usuario_id, *, actor_id):
    """Asigna un usuario a un médico que no tiene (R9, `medicos-id-no-medico`).

    Atómico, con `select_for_update` sobre el CatMedico. El DetUsuario manda
    (D8): sus nombres y su cédula NUNCA se pisan, solo se llenan los vacíos.
    Se mueven los datos personales del CatMedico al usuario y se limpian en el
    MISMO save que setea `id_usuario` (el CheckConstraint exige que un médico
    con usuario no tenga datos propios). `CatMedico.id` no cambia.

    Devuelve `(medico, descartados)`: `descartados` lista los datos del
    CatMedico que NO se movieron porque el usuario ya tenía un valor propio.
    """
    if not usuario_id:
        raise VisitDomainError("VALIDATION_ERROR", "usuarioId es requerido.", 400)

    descartados = {}
    with transaction.atomic():
        medico = CatMedico.objects.select_for_update().filter(pk=medico_id).first()
        if medico is None:
            raise VisitDomainError("MEDICO_NOT_FOUND", "Médico no encontrado.", 404)
        if medico.id_usuario_id is not None:
            raise VisitDomainError(
                "MEDICO_YA_TIENE_USUARIO", "El médico ya tiene un usuario asignado.", 409,
            )

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

        # Nombres: solo se llenan los campos VACÍOS del DetUsuario (nunca se pisa).
        det = usuario.detalle  # existe: usuario_es_medico lo exige
        det_changed = []
        for campo in ("nombre", "paterno", "materno"):
            propio = getattr(medico, campo)
            if not propio:
                continue
            if not getattr(det, campo):
                setattr(det, campo, propio)
                det_changed.append(campo)
            elif getattr(det, campo) != propio:
                descartados[campo] = propio
        if det_changed:
            det.save(update_fields=det_changed)

        # Cédula: solo si el usuario NO tiene ninguna (nunca se pisa ni se agrega).
        if medico.cedula_profesional:
            if DetUsuarioCedula.objects.filter(id_usuario=usuario).exists():
                descartados["cedulaProfesional"] = medico.cedula_profesional
            else:
                DetUsuarioCedula.objects.create(
                    id_usuario=usuario,
                    numero=medico.cedula_profesional,
                    tipo="PROFESIONAL",
                    es_principal=True,
                    orden=1,
                )

        # Escuela, sexo y fecha de nacimiento: misma regla que los nombres,
        # solo se llenan si DetUsuario no tiene.
        det_extra = []
        for campo, clave in (
            ("id_escuela_id", "escuelaId"), ("sexo", "sexo"), ("fecha_nac", "fechaNac"),
        ):
            propio = getattr(medico, campo)
            if not propio:
                continue
            if not getattr(det, campo):
                setattr(det, campo, propio)
                det_extra.append(campo.removesuffix("_id"))
            elif getattr(det, campo) != propio:
                descartados[clave] = str(propio) if clave == "fechaNac" else propio
        if det_extra:
            det.save(update_fields=det_extra)

        # Un solo UPDATE: asigna el usuario y limpia los datos propios.
        medico.id_usuario = usuario
        medico.nombre = medico.paterno = medico.materno = medico.cedula_profesional = None
        medico.id_escuela = None
        medico.sexo = medico.fecha_nac = None
        medico.updated_at = timezone.now()
        medico.updated_by_id = actor_id
        try:
            with transaction.atomic():
                medico.save(
                    update_fields=[
                        "id_usuario", "nombre", "paterno", "materno",
                        "cedula_profesional", "id_escuela", "sexo", "fecha_nac",
                        "updated_at", "updated_by_id",
                    ]
                )
        except IntegrityError:
            # Carrera: otro médico tomó al usuario entre la validación y el save.
            raise VisitDomainError(
                "MEDICO_EXISTS", "Este usuario ya tiene un perfil de médico.", 409,
            )

        transaction.on_commit(
            lambda: invalidate_identity_cache(medico_id=medico.id, usuario_id=usuario.id_usuario)
        )

    return MedicoRepository.resolve_with_detail(medico.id), descartados
