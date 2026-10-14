"""
apps/portal_citas/services/consultorios_service.py
=====================================================
Catálogo de consultorios habilitados para el canal en línea del portal
de autoservicio.

Se deriva dinámicamente de ``RelMedicoConsultorioHorario.canal`` (mismo
campo que ya usa ``slots_service`` para filtrar horarios) — deliberadamente
NO se introduce un flag nuevo en ``Consultorios`` ni en
``CatCentroAtencion``: un consultorio "existe" para el portal si tiene AL
MENOS UNA franja activa con canal ``LINEA``/``AMBOS``.

Cacheado a nivel SERVICIO (``cache.get_or_set`` sobre la lista ya
serializada), NO con ``@cache_page`` en la vista: ``cache_page`` cachearía
la respuesta HTTP completa de un endpoint autenticado con Bearer
(``PortalTokenAuthentication``), con riesgo de servir una respuesta de una
sesión a otra. El catálogo es idéntico para todos los miembros del portal,
así que se cachea el ``list[dict]``, no la respuesta HTTP. TTL 300s: el
catálogo cambia con baja frecuencia; un consultorio recién habilitado
tarda hasta 5 minutos en aparecer (aceptado, ver design doc). Redis en
producción (``backend/config/settings.py``), LocMemCache en tests.
"""

from django.core.cache import cache

from apps.catalogos.models import Consultorios
from apps.medicos.models import RelMedicoConsultorioHorario
from apps.portal_citas.errors import PortalReservaError
from apps.portal_citas.models import PortalMiembro
from apps.portal_citas.services.nucleo_service import puede_gestionar_miembro
from apps.recepcion.services.clinica_paciente_service import centro_del_paciente, centro_permitido

CACHE_KEY = "portal:consultorios:linea"
CACHE_TTL = 300


def _consultar() -> list[dict]:
    ids_consultorio = (
        RelMedicoConsultorioHorario.objects
        .filter(
            canal__in=["LINEA", "AMBOS"],
            rel_medico_consultorio__is_active=True,
        )
        .values_list("rel_medico_consultorio__consultorio_id", flat=True)
    )

    consultorios = (
        Consultorios.objects
        .filter(is_active=True, id__in=ids_consultorio)
        .select_related("id_center")
        .order_by("numero", "name")
        .distinct()
    )

    return [
        {
            "consultorioId": c.id,
            "nombre": c.name,
            "numero": c.numero,
            "centroId": c.id_center_id,
            "centroNombre": c.id_center.name if c.id_center_id else None,
        }
        for c in consultorios
    ]


def clinica_del_miembro(miembro_sesion, miembro_id) -> str | None:
    """
    Clínica (centro) del paciente para el que se está buscando horario.
    Solo se agenda en consultorios de su clínica; la reserva lo vuelve a
    validar. Un miembro ajeno a la sesión -> mismo 403 genérico que la
    reserva. ``None`` = sin dato de clínica: no se filtra.
    """
    miembro = PortalMiembro.objects.filter(id=miembro_id).first()
    if miembro is None or not puede_gestionar_miembro(miembro_sesion, miembro_id):
        raise PortalReservaError("NO_AUTORIZADO", "No puedes agendar una cita para ese miembro.", 403)
    return centro_del_paciente(miembro.no_exp, miembro.pk_num)


def listar_consultorios_en_linea(
    centro_id: int | None = None,
    *,
    centro_paciente: str | None = None,
) -> list[dict]:
    """
    Lista completa (cacheada) de consultorios habilitados para canal en
    línea. Con ``centro_id`` filtra en memoria sobre esa misma lista
    cacheada -- NO se agrega un ``.filter()`` nuevo a la BD ni una cache
    key por centro (ver design doc de ``portal-citas-filtro-clinica`):
    el dataset ya está completo en memoria, filtrar ahí es O(n) trivial
    sobre una lista de decenas de filas. ``centro_id=None`` devuelve todo
    (comportamiento previo, "Todas las clínicas").

    ``centro_paciente`` (ver ``clinica_del_miembro``) deja solo los de la
    clínica del paciente; también se filtra en memoria.
    """
    datos = cache.get_or_set(CACHE_KEY, _consultar, CACHE_TTL)
    if centro_paciente is not None:
        datos = [c for c in datos if centro_permitido(centro_paciente, c["centroId"])]
    if centro_id is None:
        return datos
    return [c for c in datos if c["centroId"] == centro_id]


def listar_centros_en_linea(*, centro_paciente: str | None = None) -> list[dict]:
    """
    Catálogo de centros de atención con AL MENOS UN consultorio habilitado
    para canal en línea, derivado por dedup en memoria de la MISMA lista
    cacheada que usa ``listar_consultorios_en_linea`` -- no una query
    propia contra ``CatCentroAtencion``. Garantiza que el selector de
    clínica y el filtro de consultorios compartan una única fuente de
    verdad (imposible que el selector ofrezca una clínica cuyo filtro
    devuelva ``[]``). Descarta ``centroNombre=None`` (FK huérfana,
    ``id_center`` nulo) y ordena por nombre.
    """
    vistos: set[int] = set()
    centros: list[dict] = []
    for c in listar_consultorios_en_linea(centro_paciente=centro_paciente):
        centro_id = c["centroId"]
        if centro_id is not None and centro_id not in vistos:
            vistos.add(centro_id)
            centros.append({"centroId": centro_id, "nombre": c["centroNombre"]})
    return sorted(centros, key=lambda x: x["nombre"] or "")

