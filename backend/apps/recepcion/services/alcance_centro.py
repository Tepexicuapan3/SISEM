"""
Alcance por centro de atención en Recepción.

El alcance general (qué centros tiene cada usuario) vive en
``apps.authentication.services.centro_scope``; aquí van las reglas de
Recepción que lo usan:

- Cada visita y cada cita guardan el centro donde se registraron: el del
  consultorio y, sin consultorio, el de quien la registra. No cambia después.
- Un registro de otro centro responde como si no existiera (404).
- Las visitas (check-in) se registran solo en centros del alcance.
- Las citas también, salvo con ``recepcion:citas:agendar_otros_centros``, que
  deja agendar (y ver horarios) en otros centros sin ampliar lo que se ve.
"""

from apps.authentication.services.authorization_service import has_capability
from apps.authentication.services.centro_scope import AlcanceCentros, centro_principal
from apps.recepcion.services.errors import VisitDomainError

PERMISO_AGENDAR_OTROS_CENTROS = "recepcion:citas:agendar_otros_centros"

_TODOS = AlcanceCentros(todos=True, centros=frozenset())


def centro_de_consultorio(consultorio_id) -> int | None:
    if consultorio_id is None:
        return None
    from apps.catalogos.models.consultorios import Consultorios

    return Consultorios.objects.filter(pk=consultorio_id).values_list("id_center_id", flat=True).first()


def centro_de_registro(consultorio_id, created_by_id) -> int | None:
    """Centro que se guarda al crear una visita o una cita."""
    return centro_de_consultorio(consultorio_id) or centro_principal(created_by_id)


def exigir_en_alcance(alcance: AlcanceCentros, centro_id, *, code: str, message: str) -> None:
    """Un registro fuera del alcance no existe para quien consulta."""
    if not alcance.permite(centro_id):
        raise VisitDomainError(code, message, 404)


def _exigir_destino(alcance: AlcanceCentros, consultorio_id) -> None:
    destino = centro_de_consultorio(consultorio_id) or alcance.principal
    if destino is None and not alcance.todos:
        raise VisitDomainError(
            "CENTRO_NO_ASIGNADO",
            "No tienes un centro de atención asignado. Pide a un administrador que te asigne uno.",
            403,
        )
    if destino is not None and not alcance.permite(destino):
        raise VisitDomainError(
            "CENTRO_NO_PERMITIDO",
            "El consultorio pertenece a otro centro de atención.",
            403,
        )


def exigir_centro_para_registrar(alcance: AlcanceCentros, consultorio_id) -> None:
    """Check-in: la visita se registra en un centro del alcance."""
    _exigir_destino(alcance, consultorio_id)


def puede_agendar_en_otros_centros(permisos) -> bool:
    return has_capability(permisos or [], PERMISO_AGENDAR_OTROS_CENTROS)


def exigir_centro_para_agendar(alcance: AlcanceCentros, permisos, consultorio_id) -> None:
    if puede_agendar_en_otros_centros(permisos):
        return
    _exigir_destino(alcance, consultorio_id)


def alcance_para_agendar(alcance: AlcanceCentros, permisos) -> AlcanceCentros:
    """Horarios que se muestran al agendar: todos si puede agendar en otros centros."""
    return _TODOS if puede_agendar_en_otros_centros(permisos) else alcance
