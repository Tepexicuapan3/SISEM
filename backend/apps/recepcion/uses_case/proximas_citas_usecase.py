"""
Próximas citas (recepción): las citas agendadas o confirmadas de los
próximos días, para saber quién viene sin tener que buscar paciente por
paciente. Incluye las que deja el médico al cerrar la consulta (P-12),
marcadas como seguimiento.

El nombre del paciente sale de SERMED (una consulta por paciente distinto
de la página, nunca por cita repetida). Si SERMED falla, el nombre queda
vacío y la lista se sirve igual.
"""

import logging
import math

from django.utils import timezone

from apps.consulta_medica.services.paciente_entrada import llave_publica
from apps.recepcion.models import MOTIVO_CITA_SEGUIMIENTO, CitaMedica, EstatusCita
from apps.recepcion.repositories.citas_repository import _serialize_cita
from apps.recepcion.services.vigencia_service import buscar_fila_paciente

logger = logging.getLogger(__name__)

ESTATUS_PROXIMAS = (EstatusCita.AGENDADA, EstatusCita.CONFIRMADA)


def _nombre_paciente(no_exp, pk_num) -> str:
    try:
        fila = buscar_fila_paciente(no_exp, pk_num)
    except Exception:
        logger.exception("Error consultando expediente %s para próximas citas", no_exp)
        return ""
    if not fila:
        return ""
    partes = [fila.get("DS_PATERNO", ""), fila.get("DS_MATERNO", ""), fila.get("DS_NOMBRE", "")]
    return " ".join(p for p in partes if p).strip()


def list_proximas_citas(
    alcance,
    *,
    fecha_desde,
    fecha_hasta,
    page,
    page_size,
    medico_id=None,
    solo_seguimiento=False,
) -> tuple[list[dict], int, int]:
    qs = (
        CitaMedica.objects
        .filter(alcance.q("centro_id"))
        .filter(
            estatus__in=ESTATUS_PROXIMAS,
            fecha_hora__date__gte=fecha_desde,
            fecha_hora__date__lte=fecha_hasta,
            fecha_hora__gte=timezone.now(),
        )
        .select_related("patient", "medico__id_usuario__detalle", "consultorio")
        .order_by("fecha_hora")
    )
    if medico_id:
        qs = qs.filter(medico_id=medico_id)
    if solo_seguimiento:
        qs = qs.filter(motivo=MOTIVO_CITA_SEGUIMIENTO)

    total = qs.count()
    start = (page - 1) * page_size
    nombres: dict[tuple, str] = {}
    items = []
    for cita in qs[start: start + page_size]:
        llave = llave_publica(cita)
        if llave not in nombres:
            nombres[llave] = _nombre_paciente(*llave)
        items.append({
            **_serialize_cita(cita),
            "pacienteNombre": nombres[llave],
            "esSeguimiento": cita.motivo == MOTIVO_CITA_SEGUIMIENTO,
        })
    total_pages = math.ceil(total / page_size) if total else 0
    return items, total, total_pages
