"""
Seguimientos por agendar (recepción): el médico indicó una fecha de
seguimiento al cerrar la nota pero no quedó cita. Pasa cuando no eligió
horario o cuando el paciente tiene otro consultorio familiar (P-03: la cita
la agenda recepción, en el consultorio familiar).

Las fechas salen del contrato de consulta médica (``seguimientos_indicados``).
Una nota deja de estar pendiente cuando tiene una cita de seguimiento vigente,
con la misma convención que la cita que deja el médico: motivo
``MOTIVO_CITA_SEGUIMIENTO`` y notas "Consulta <folio de la visita>". Si esa
cita se cancela, vuelve a estar pendiente.
"""

import math

from django.utils import timezone

from apps.consulta_medica.services.seguimientos_contract import seguimientos_indicados
from apps.recepcion.models import MOTIVO_CITA_SEGUIMIENTO, CitaMedica, EstatusCita
from apps.recepcion.uses_case.agendar_cita_usecase import notas_de_cita_de_seguimiento
from apps.recepcion.uses_case.proximas_citas_usecase import _nombre_paciente


def _con_cita(folios) -> set[str]:
    notas = {notas_de_cita_de_seguimiento(f): f for f in folios}
    agendadas = (
        CitaMedica.objects
        .filter(motivo=MOTIVO_CITA_SEGUIMIENTO, notas__in=notas.keys())
        .exclude(estatus=EstatusCita.CANCELADA)
        .values_list("notas", flat=True)
    )
    return {notas[n] for n in agendadas}


def list_seguimientos_por_agendar(alcance, *, fecha_desde, fecha_hasta, page, page_size):
    indicados = seguimientos_indicados(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, alcance=alcance)
    con_cita = _con_cita([s["visitFolio"] for s in indicados])
    pendientes = [s for s in indicados if s["visitFolio"] not in con_cita]

    total = len(pendientes)
    start = (page - 1) * page_size
    hoy = timezone.localdate()
    nombres: dict[tuple, str] = {}
    items = []
    for seguimiento in pendientes[start: start + page_size]:
        llave = (seguimiento["noExp"], seguimiento["pkNum"])
        if llave not in nombres:
            nombres[llave] = _nombre_paciente(*llave)
        fecha = seguimiento["fechaSeguimiento"]
        items.append({
            **seguimiento,
            "fechaSeguimiento": fecha.isoformat(),
            "fechaConsulta": seguimiento["fechaConsulta"].isoformat() if seguimiento["fechaConsulta"] else None,
            "pacienteNombre": nombres[llave],
            "vencido": fecha < hoy,
        })
    total_pages = math.ceil(total / page_size) if total else 0
    return items, total, total_pages
