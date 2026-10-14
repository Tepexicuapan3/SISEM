"""
apps/portal_citas/services/slots_service.py
===============================================
Disponibilidad de horarios para el portal de autoservicio (Fase 3).

Replica el patrón de consulta de
``apps.recepcion.repositories.citas_repository.CitasRepository.get_slots_disponibles``
(mismo modelo ``HorarioDisponible``), agregando el filtro de canal apto
para portal.

PATCH (calendario visual disponible/ocupado): se retiró el filtro
``disponible=True`` de la query para que el endpoint traiga TAMBIÉN los
slots ocupados de la fecha consultada — así el frontend puede pintar el
calendario completo (verde/rojo) en vez de solo mostrar huecos sin
contexto. El campo de salida ``estado`` ahora refleja el valor real de
``HorarioDisponible.disponible`` (``"disponible"`` / ``"ocupado"``) en vez
de estar hardcodeado.

Deliberadamente SIGUE sin exponer quién ocupa un slot ocupado: el dict de
salida es exactamente el mismo shape que antes (``slotId, fecha, hora,
consultorioNombre, especialidadPrincipal, estado``). La query NO hace
join con ``CitaMedica`` ni con datos del paciente — el ``select_related``
sigue limitado a ``medico`` y ``consultorio`` — así que no hay forma de
que un ``no_exp``, folio de cita o nombre de paciente se filtre en la
respuesta de un slot ocupado.

PATCH (Portal de Citas — filtro por Clínica + privacidad del médico): se
elimina la key ``medicoNombre`` del dict de salida. El nombre del médico
NUNCA debe viajar al navegador antes de que el paciente reserve — la
regla se aplica en el servicio (el único lugar donde es verificable que
el dato no se produce), no con un flag opcional en la vista/serializer.
El médico reaparece recién en la respuesta de ``POST /portal/citas``
(``reservar_cita_usecase``) y en ``GET /portal/citas``
(``listar_citas_usecase``) -- esos dos módulos NO se tocan, siguen
devolviendo ``medicoNombre`` sin cambios. ``select_related("medico__...")``
se mantiene: ``_especialidad_principal_nombre(slot.medico)`` lo sigue
necesitando para armar ``especialidadPrincipal``.

PATCH (post-verificación de Fase 3): el parámetro original ``servicioTipo``
solo hacía eco del valor recibido porque ``servicio_tipo`` (con choices
medicina_general/especialidad/urgencias) vive ÚNICAMENTE en ``CitaMedica`` y
no es una propiedad inherente del médico ni del horario. Se investigó y SÍ
existe un catálogo real de especialidades ya conectado a los médicos:
``apps.catalogos.models.Especialidades`` + ``apps.medicos.models.RelMedicoEspecialidad``
(tabla puente ``medico``/``especialidad``/``es_principal``). Se reemplazó el
parámetro por ``especialidad_id`` (filtro real) y el campo de salida
``servicioTipo`` (eco) por ``especialidadPrincipal`` (nombre de la
especialidad principal del médico, o el label de generalista si no tiene
ninguna — ver ``_especialidad_principal_nombre``).

Regla para la Fase 4 (NO implementada acá, solo documentada — la reserva de
citas es fase 4): al crear ``CitaMedica``, ``servicio_tipo`` debe derivarse
del médico elegido: si tiene AL MENOS UNA fila en ``RelMedicoEspecialidad``
-> ``"especialidad"``; si no tiene ninguna -> ``"medicina_general"``.
``"urgencias"`` queda fuera del alcance del portal (no seleccionable desde
acá — se asume manejo presencial en recepción; confirmar con el usuario
antes de dar esto por definitivo en la Fase 4).

PATCH (Portal de Citas — Disponibilidad por Consultorio): el eje de
filtro pasa a ser ``consultorio_id`` (FK directo de ``HorarioDisponible``,
soportado por el índice ``hd_consult_fecha_canal_idx``).
``especialidad_id`` se mantiene funcional como parámetro # DEPRECATED
durante una release de transición: un cliente legado que solo mande
``especialidadId`` sigue funcionando, y ambos filtros son combinables
(AND) si el cliente manda los dos. Se remueve una release después de
desplegar el portal nuevo. También se agrega
``get_disponibilidad_mensual`` para la agregación server-side que consume
el calendario mensual del frontend.
"""

import calendar
from datetime import date
from typing import Optional

from django.db.models import Count

from apps.medicos.models import CatMedico
from apps.recepcion.models import HorarioDisponible
from apps.recepcion.repositories.citas_repository import q_slots_futuros

SIN_ESPECIALIDAD_LABEL = "Medicina General"


def _especialidad_principal_nombre(medico: CatMedico) -> Optional[str]:
    """
    Nombre de la especialidad principal del médico (``es_principal=True``),
    o ``SIN_ESPECIALIDAD_LABEL`` si el médico no tiene ninguna especialidad
    asignada en ``RelMedicoEspecialidad`` (se lo trata como generalista de
    medicina general). Si tiene especialidades pero ninguna marcada como
    principal, se usa la primera como fallback razonable en vez de mostrar
    ``None`` (evita "perder" la información en la respuesta del slot).
    """
    especialidades = list(medico.especialidades.select_related("especialidad").all())
    if not especialidades:
        return SIN_ESPECIALIDAD_LABEL

    principal = next((e for e in especialidades if e.es_principal), especialidades[0])
    return principal.especialidad.name


def get_slots_portal(
    fecha: date,
    consultorio_id: Optional[int] = None,
    especialidad_id: Optional[int] = None,
) -> list[dict]:
    slots = (
        HorarioDisponible.objects
        .filter(
            fecha=fecha,
            canal__in=["LINEA", "AMBOS"],
        )
        # Un horario que ya pasó no se puede reservar: ni se muestra.
        .filter(q_slots_futuros())
        # Bloqueado por una ausencia del médico: no es "ocupado", no se ofrece.
        .filter(bloqueado_por_excepcion__isnull=True)
        # Médico de baja, suspendido, etc.: sus horarios no se ofrecen.
        .filter(medico__estatus_medico="ACTIVO")
        .select_related("medico__id_usuario__detalle", "consultorio")
        .order_by("hora")
    )

    if consultorio_id is not None:
        slots = slots.filter(consultorio_id=consultorio_id)

    # DEPRECATED: se mantiene funcional durante una release de transición
    # para clientes legados que aún filtran por especialidad (ver nota de
    # módulo). Combinable (AND) con consultorio_id si el cliente manda
    # ambos — no hay conflicto lógico entre los dos filtros.
    if especialidad_id is not None:
        slots = slots.filter(medico__especialidades__especialidad_id=especialidad_id)

    resultado = []
    for slot in slots:
        resultado.append({
            "slotId": slot.id,
            "fecha": str(slot.fecha),
            "hora": str(slot.hora)[:5],
            "consultorioNombre": slot.consultorio.name if slot.consultorio else None,
            "especialidadPrincipal": _especialidad_principal_nombre(slot.medico),
            "estado": "disponible" if slot.disponible else "ocupado",
        })

    return resultado


def get_disponibilidad_mensual(consultorio_id: int, anio: int, mes: int) -> list[dict]:
    """
    Conteo agregado de slots disponibles por fecha, para un consultorio y
    mes/año dados — una sola query agregada server-side (``values``
    + ``annotate(Count)``), sin transferir los slots individuales del mes
    completo (el calendario del frontend solo necesita ``{fecha: N}``).

    Usa ``fecha__range`` con los límites exactos del mes (vía
    ``calendar.monthrange``) en vez de ``fecha__year``/``fecha__month``:
    estos últimos envuelven la columna en ``EXTRACT()`` e inutilizan el
    índice compuesto ``hd_consult_fecha_canal_idx`` (consultorio, fecha,
    canal) — un range scan sobre ``fecha`` sí lo usa.

    Solo cuenta slots ``disponible=True`` con canal apto para portal
    (``LINEA``/``AMBOS``); un consultorio inexistente o sin slots en el
    mes simplemente no aporta filas (lista vacía, no error — la vista es
    responsable de no distinguir "no existe" de "sin cupo" para no
    habilitar enumeración).
    """
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    filas = (
        HorarioDisponible.objects
        .filter(
            consultorio_id=consultorio_id,
            canal__in=["LINEA", "AMBOS"],
            disponible=True,
            fecha__range=(primer_dia, ultimo_dia),
            medico__estatus_medico="ACTIVO",
        )
        .filter(q_slots_futuros())
        .values("fecha")
        .annotate(total=Count("id"))
        .order_by("fecha")
    )

    return [{"fecha": str(f["fecha"]), "slotsDisponibles": f["total"]} for f in filas]
