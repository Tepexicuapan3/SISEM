"""
apps/portal_citas/uses_case/listar_citas_usecase.py
========================================================
Listado de citas del núcleo familiar de la sesión de portal (Fase 8 —
endpoint que faltó en las fases originales: el frontend necesita una
pantalla de "mis citas" para poder ofrecer la cancelación, y hasta ahora
solo existían ``POST /portal/citas`` (reservar, Fase 4) y
``PATCH /portal/citas/{folio}/cancelar`` (cancelar, Fase 6) — nunca un
``GET`` para listar).

Regla de la query: todos los integrantes del mismo núcleo comparten el
MISMO ``no_exp`` (es la razón de ser de la regla de autorización de
``nucleo_service`` — ver su docstring), así que alcanza con fijar
``no_exp=miembro_sesion.no_exp`` + filtrar por la lista de ``pk_num``
gestionables (``nucleo_service._pk_nums_gestionables``, misma regla de
autorización que ``obtener_nucleo``/``puede_gestionar_miembro`` — no se
reimplementa acá) en vez de armar pares ``(no_exp, pk_num)``.

Orden: más recientes/próximas primero (``-fecha_hora``) — es el criterio
más útil para "mis citas": lo primero que un paciente quiere ver es su
próxima cita agendada, no una atendida hace un año.

``cancelable`` se calcula acá (no en el frontend) reusando exactamente la
misma regla que ``cancelar_cita_usecase`` (estatus en
``ESTATUS_CANCELABLES`` + ventana mínima ``PORTAL_CANCELACION_VENTANA_HORAS``)
para que el frontend solo tenga que leer un booleano y decidir si muestra
el botón de cancelar, sin duplicar la lógica de negocio ni adivinar.

No se devuelve ``medicoNombre``: el portal público de pacientes no
muestra el nombre del médico en NINGÚN punto del flujo, tampoco en el
historial de "Mis citas" ya reservadas. Esa información solo la ve el
personal de recepción en la ficha del check-in por QR
(``apps.recepcion.uses_case.qr_checkin_usecase``), que es un módulo
independiente del sistema interno.

``ESTATUS_CANCELABLES`` se importa de ``cancelar_cita_usecase`` (no se
redefine acá) para que exista una única fuente de verdad: dos tuplas
idénticas mantenidas a mano en dos módulos inevitablemente terminan
divergiendo el día que alguien cambia una sin acordarse de la otra.

Fuera de alcance: no se toca la lógica de reserva (Fase 4) ni de
cancelación (Fase 6), este módulo es de solo lectura.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.portal_citas.models import PortalMiembro
from apps.portal_citas.services.nucleo_service import _pk_nums_gestionables, obtener_nucleo
from apps.portal_citas.uses_case.cancelar_cita_usecase import ESTATUS_CANCELABLES
from apps.recepcion.models import CitaMedica
from apps.consulta_medica.services.paciente_entrada import llave_publica
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp


def _es_cancelable(cita: CitaMedica, ahora, ventana: timedelta) -> bool:
    if cita.estatus not in ESTATUS_CANCELABLES:
        return False
    return cita.fecha_hora - ahora >= ventana


def listar_citas(miembro_sesion: PortalMiembro) -> list[dict]:
    no_exp = miembro_sesion.no_exp
    pk_nums = _pk_nums_gestionables(miembro_sesion)

    # Fuerza (get_or_create interno) que exista un PortalMiembro para cada
    # persona visible del núcleo -- necesario para poder mapear
    # no_exp+pk_num -> nombre_visible más abajo aunque la sesión actual
    # nunca haya llamado antes GET /portal/nucleo. Mismo mecanismo que ya
    # dispara cada reserva/cancelación vía puede_gestionar_miembro.
    obtener_nucleo(miembro_sesion)

    nombres_por_pk = dict(
        PortalMiembro.objects.filter(no_exp=no_exp, pk_num__in=pk_nums).values_list(
            "pk_num", "nombre_visible"
        )
    )

    citas = (
        # Plan contraer la llave vieja: la cita se liga por cns_paciente.
        CitaMedica.objects.filter(patient__no_exp=normalizar_no_exp(no_exp), patient__pk_num__in=pk_nums)
        .select_related("patient", "medico__id_usuario__detalle", "consultorio")
        .order_by("-fecha_hora")
    )

    ahora = timezone.now()
    ventana = timedelta(hours=settings.PORTAL_CANCELACION_VENTANA_HORAS)

    return [
        {
            "folio": cita.folio,
            "fechaHora": cita.fecha_hora.isoformat(),
            "consultorioNombre": cita.consultorio.name if cita.consultorio else None,
            "servicioTipo": cita.servicio_tipo,
            "estatus": cita.estatus,
            "paraQuien": nombres_por_pk.get(llave_publica(cita)[1]),
            "cancelable": _es_cancelable(cita, ahora, ventana),
        }
        for cita in citas
    ]
