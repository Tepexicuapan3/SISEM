"""
Construcción de los dicts de respuesta (capa de presentación) para el
catálogo de médicos. Separado de `views/` para que las vistas queden como
transporte puro (auth + delegar a uses_case + formatear respuesta) y de
`uses_case/` para que la lógica de negocio no dependa de la forma exacta
del JSON expuesto.
"""

import logging

from apps.medicos import identity
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoCobertura

logger = logging.getLogger(__name__)


def _consultorio_or_none(rmc: RelMedicoConsultorio):
    # La FK es db_constraint=False: la BD admite filas que apuntan a un
    # consultorio inexistente. Una huérfana no debe tumbar el endpoint.
    try:
        return rmc.consultorio
    except RelMedicoConsultorio.consultorio.RelatedObjectDoesNotExist:
        logger.warning(
            "rel_medico_consultorio id=%s apunta a consultorio inexistente id=%s",
            rmc.id, rmc.consultorio_id,
        )
        return None


def serialize_medico(medico: CatMedico) -> dict:
    usuario = medico.id_usuario
    det = getattr(usuario, "detalle", None) if usuario is not None else None
    # `.all()` + filtro/orden en Python: `.filter()/.order_by()/.select_related()`
    # sobre el manager relacionado anulan el prefetch de `list_queryset` (N+1).
    cedulas = sorted(usuario.cedulas.all(), key=lambda c: c.orden) if usuario is not None else []
    especialidades = list(medico.especialidades.all())
    centros = [c for c in medico.centros.all() if c.is_active]
    consultorios_activos = [
        c for c in medico.consultorios.all()
        if c.is_active and _consultorio_or_none(c) is not None
    ]
    partes = identity.nombre_partes(medico)

    # Con usuario manda DetUsuario; sin usuario, la escuela propia del médico.
    # getattr con default: la FK es db_constraint=False y una huérfana lanza
    # RelatedObjectDoesNotExist (subclase de AttributeError).
    escuela = getattr(det if usuario is not None else medico, "id_escuela", None)

    return {
        # Contrato unificado: "id" es SIEMPRE CatMedico.id (No. Médico).
        # "usuarioId" es el SyUsuario asociado, null en médicos sin usuario.
        "id": medico.id,
        "usuarioId": medico.id_usuario_id,
        "tieneUsuario": usuario is not None,
        "username": usuario.usuario if usuario is not None else None,
        "nombreCompleto": identity.display_name(medico),
        "nombre": partes.nombre or "",
        "paterno": partes.paterno or "",
        "materno": partes.materno or "",
        "cedulaProfesional": identity.cedula_profesional(medico),
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


def serialize_consultorio_asignacion(rmc: RelMedicoConsultorio) -> dict:
    # En el detalle la huérfana SÍ se expone (con nulls) para poder eliminarla.
    consultorio = _consultorio_or_none(rmc)
    return {
        "id": rmc.id,
        "consultorioId": rmc.consultorio_id,
        "consultorioNumero": consultorio.numero if consultorio else None,
        "consultorioNombre": consultorio.name if consultorio else None,
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


def serialize_especialidad(rel) -> dict:
    return {
        "id": rel.id,
        "especialidadId": rel.especialidad_id,
        "name": rel.especialidad.name,
        "esPrincipal": rel.es_principal,
    }


def serialize_centro(rel) -> dict:
    return {
        "id": rel.id,
        "centroId": rel.centro_id,
        "centroNombre": rel.centro.name,
        "tipoAdscripcion": rel.tipo_adscripcion,
        "fechaInicio": str(rel.fecha_inicio),
        "fechaFin": str(rel.fecha_fin) if rel.fecha_fin else None,
    }


def serialize_excepcion(exc) -> dict:
    return {
        "id": exc.id,
        "tipo": exc.tipo,
        "fechaInicio": str(exc.fecha_inicio),
        "fechaFin": str(exc.fecha_fin),
        "horaInicio": str(exc.hora_inicio) if exc.hora_inicio else None,
        "horaFin": str(exc.hora_fin) if exc.hora_fin else None,
        "motivo": exc.motivo,
        "consultorioId": exc.consultorio_id,
    }


def serialize_excepcion_created(exc) -> dict:
    """Forma reducida que devuelve el POST -- distinta del listado (ver
    contrato preexistente: el POST nunca expuso horaInicio/horaFin/motivo/
    consultorioId, solo id/tipo/fechaInicio/fechaFin)."""
    return {
        "id": exc.id,
        "tipo": exc.tipo,
        "fechaInicio": str(exc.fecha_inicio),
        "fechaFin": str(exc.fecha_fin),
    }


def serialize_cobertura(cob: RelMedicoCobertura) -> dict:
    return {
        "id": cob.id,
        "medicoSuplenteId": cob.medico_suplente_id,
        "medicoSuplenteNombre": identity.display_name(cob.medico_suplente),
        "medicoTitularId": cob.medico_titular_id,
        "medicoTitularNombre": identity.display_name(cob.medico_titular),
        "consultorioId": cob.consultorio_id,
        "consultorioNombre": cob.consultorio.name if cob.consultorio_id else None,
        "centroId": cob.centro_id,
        "centroNombre": cob.centro.name if cob.centro_id else None,
        "fechaInicio": str(cob.fecha_inicio),
        "fechaFin": str(cob.fecha_fin) if cob.fecha_fin else None,
        "motivo": cob.motivo,
        "isActive": cob.is_active,
        "horarios": [
            {
                "id": h.id,
                "diaSemana": h.dia_semana,
                "horaInicio": str(h.hora_inicio),
                "horaFin": str(h.hora_fin),
            }
            for h in cob.horarios.all().order_by("dia_semana", "hora_inicio")
        ],
        "createdAt": cob.created_at.isoformat() if cob.created_at else None,
    }
