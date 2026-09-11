"""
Traducción explícita entre los dos espacios de identidad que el catálogo de
médicos deja de compartir a partir del cambio `medico-pk-independiente`:

- "espacio usuario": `authentication.SyUsuario.id_usuario` (login, `doctor_id`
  en `recepcion.Visit`/`consulta_medica.VisitConsultation`).
- "espacio médico": `medicos.CatMedico.id` (PK surrogate, `medico_id` en las
  9 columnas FK del catálogo — especialidades, centros, consultorios,
  excepciones, coberturas, citas, slots, consumos de insumos).

Antes de este cambio ambos números coincidían siempre (`CatMedico.id_usuario`
era la PK). Después, son espacios de ids DISTINTOS y numéricamente pueden no
coincidir. Mezclarlos sin traducir no rompe ninguna FK (ambos ids siguen
siendo "válidos" en abstracto) — asigna una cita/slot/consumo a la PERSONA
EQUIVOCADA en silencio. Es el riesgo R1 de la propuesta (obs #467) y el
requirement crítico #5 de la spec (obs #468).

Regla dura: ningún código de aplicación pasa un id de un espacio al otro
directamente. Todo pasa por acá.

Ver Engram, sdd/medico-pk-independiente/design, sección "D6 — Módulo de
traducción de identidades".
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.core.cache import cache

logger = logging.getLogger(__name__)

# TTL corto: el catálogo de médicos es chico y casi estático, pero no es
# inmutable (altas/bajas, reasignación de usuario). Cache por request/proceso
# vía django.core.cache (locmem/redis según settings), no un dict global en
# memoria de proceso -- evita servir un mapeo stale entre workers.
_CACHE_TTL_SECONDS = 30
_CACHE_PREFIX = "medicos:identity"


def _cache_key_medico_by_usuario(usuario_id: int) -> str:
    return f"{_CACHE_PREFIX}:medico_for_usuario:{usuario_id}"


def _cache_key_usuario_by_medico(medico_id: int) -> str:
    return f"{_CACHE_PREFIX}:usuario_for_medico:{medico_id}"


def medico_id_for_usuario(usuario_id: int | None) -> int | None:
    """
    Traduce un id de usuario (espacio SyUsuario/doctor_id) a la PK surrogate
    de CatMedico. Devuelve None si `usuario_id` es None o si ese usuario no
    tiene perfil de médico en el catálogo (usuario que no es médico, o
    médico dado de baja del catálogo).
    """
    if usuario_id is None:
        return None

    cache_key = _cache_key_medico_by_usuario(usuario_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != 0 else None

    from apps.medicos.models import CatMedico

    medico_id = (
        CatMedico.objects.filter(id_usuario_id=usuario_id).values_list("id", flat=True).first()
    )
    # 0 es un centinela ("consultado, no encontrado") para no perder cache
    # en el caso None -- django.core.cache.get() no distingue "no está" de
    # "está guardado como None" en todos los backends.
    cache.set(cache_key, medico_id if medico_id is not None else 0, _CACHE_TTL_SECONDS)
    return medico_id


def usuario_id_for_medico(medico_id: int | None) -> int | None:
    """
    Traduce una PK surrogate de CatMedico a su id de usuario (espacio
    SyUsuario/doctor_id). Devuelve None si `medico_id` es None o si ese
    médico no tiene usuario asociado (id_usuario NULL -- médico sin cuenta
    de sistema, habilitado por este mismo cambio).
    """
    if medico_id is None:
        return None

    cache_key = _cache_key_usuario_by_medico(medico_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != 0 else None

    from apps.medicos.models import CatMedico

    usuario_id = (
        CatMedico.objects.filter(id=medico_id).values_list("id_usuario_id", flat=True).first()
    )
    cache.set(cache_key, usuario_id if usuario_id is not None else 0, _CACHE_TTL_SECONDS)
    return usuario_id


def medico_ids_for_usuarios(usuario_ids: Iterable[int]) -> dict[int, int]:
    """
    Versión bulk de `medico_id_for_usuario` -- evita N+1 al resolver un lote
    de usuario_ids (p.ej. `disponibilidad.get_medicos_disponibles`). Solo
    incluye en el resultado los usuario_ids que SÍ tienen médico asociado.
    """
    ids = [uid for uid in usuario_ids if uid is not None]
    if not ids:
        return {}

    from apps.medicos.models import CatMedico

    return dict(
        CatMedico.objects.filter(id_usuario_id__in=ids).values_list("id_usuario_id", "id")
    )


def display_name(medico) -> str:
    """
    Nombre a mostrar para un médico, con cadena de fallback (cierre de R5 --
    riesgo de médico sin usuario apareciendo sin nombre en agenda/PDF/ficha):

      1. `det.nombre_completo` (DetUsuario del usuario asociado, si existe)
      2. `id_usuario.usuario` (username, si hay usuario pero sin detalle)
      3. `medico.nombre_display` (campo propio del catálogo, pensado para
         médicos SIN usuario -- ver F4-10/models.py)
      4. `f"Médico #{medico.id}"` (último recurso, nunca revienta la UI)
    """
    usuario = getattr(medico, "id_usuario", None)
    if usuario is not None:
        det = getattr(usuario, "detalle", None)
        if det is not None and det.nombre_completo:
            return det.nombre_completo
        if usuario.usuario:
            return usuario.usuario

    if getattr(medico, "nombre_display", None):
        return medico.nombre_display

    return f"Médico #{medico.id}"
