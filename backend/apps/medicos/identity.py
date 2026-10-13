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

Actualización (cambio `medicos-id-no-medico`): `CatMedico.id` pasa a ser el
No. Médico legado (`no_medico`, 1..2726) y la secuencia continúa desde ahí.
Los dos espacios siguen siendo DISTINTOS (id de médico != id de usuario) y la
regla dura de arriba no cambia: el id de médico ya no es un surrogate opaco
sino el número que el legado conoce, y los médicos sin usuario (id_usuario
NULL) no tienen contraparte en el espacio usuario, por lo que no pueden ser
`doctor_id` de una visita. Ver sdd/medicos-id-no-medico/design.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.core.cache import cache
from django.db.models import CharField, F, Value
from django.db.models.functions import Coalesce, Concat, NullIf, Replace, Trim

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


def invalidate_identity_cache(*, medico_id: int | None = None, usuario_id: int | None = None) -> None:
    """Borra las claves de cache del mapeo usuario<->medico (ej. tras asignar un usuario)."""
    keys = []
    if medico_id is not None:
        keys.append(_cache_key_usuario_by_medico(medico_id))
    if usuario_id is not None:
        keys.append(_cache_key_medico_by_usuario(usuario_id))
    if keys:
        cache.delete_many(keys)


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


# ─── DATOS DE IDENTIDAD (nombre / cédula) ───────────────────────────────────
#
# Único punto de lectura del nombre y la cédula de un médico. Con usuario la
# fuente es DetUsuario / DetUsuarioCedula; sin usuario (médicos que entran por
# el import Excel) son los campos propios de CatMedico. Ningún helper hace
# `.filter/.order_by/.select_related` sobre managers relacionados: eso anula
# el prefetch del caller y genera N+1. Los callers agregan los
# select_related / prefetch con IDENTITY_SELECT / IDENTITY_PREFETCH.

IDENTITY_SELECT = ("id_usuario", "id_usuario__detalle")
IDENTITY_PREFETCH = ("id_usuario__cedulas",)


@dataclass(frozen=True)
class NombrePartes:
    nombre: str | None = None
    paterno: str | None = None
    materno: str | None = None


def with_identity(qs, prefix: str = ""):
    """select_related del usuario y su detalle; `prefix` para FKs a médico (ej. "surgeon__")."""
    return qs.select_related(f"{prefix}id_usuario__detalle")


def nombre_partes(medico) -> NombrePartes:
    """Nombre/paterno/materno: del DetUsuario si hay usuario, de CatMedico si no."""
    usuario = getattr(medico, "id_usuario", None)
    if usuario is not None:
        det = getattr(usuario, "detalle", None)
        if det is None:
            return NombrePartes()
        return NombrePartes(det.nombre or None, det.paterno or None, det.materno or None)
    return NombrePartes(
        getattr(medico, "nombre", None) or None,
        getattr(medico, "paterno", None) or None,
        getattr(medico, "materno", None) or None,
    )


def display_name(medico) -> str:
    """
    Nombre a mostrar para un médico. Nunca lanza excepción por usuario ausente:

      1. `det.nombre_completo` (DetUsuario del usuario asociado, si existe)
      2. `id_usuario.usuario` (username, si hay usuario pero sin detalle)
      3. "nombre paterno materno" de CatMedico (médico SIN usuario)
      4. `f"Médico #{medico.id}"` (último recurso, nunca revienta la UI)
    """
    usuario = getattr(medico, "id_usuario", None)
    if usuario is not None:
        det = getattr(usuario, "detalle", None)
        if det is not None and det.nombre_completo:
            return det.nombre_completo
        if usuario.usuario:
            return usuario.usuario
    else:
        partes = nombre_partes(medico)
        propio = " ".join(p for p in (partes.nombre, partes.paterno, partes.materno) if p)
        if propio:
            return propio

    return f"Médico #{medico.id}"


def cedula_profesional(medico) -> str | None:
    """
    Cédula profesional del médico o None. Con usuario: la principal de
    DetUsuarioCedula, o la primera de tipo PROFESIONAL (por `orden`); se itera
    `cedulas.all()` para respetar el prefetch (IDENTITY_PREFETCH). Sin usuario:
    campo propio de CatMedico.
    """
    usuario = getattr(medico, "id_usuario", None)
    if usuario is None:
        return getattr(medico, "cedula_profesional", None) or None

    cedulas = sorted(usuario.cedulas.all(), key=lambda c: c.orden)
    for c in cedulas:
        if c.es_principal and c.numero:
            return c.numero
    for c in cedulas:
        if (c.tipo or "").strip().upper() == "PROFESIONAL" and c.numero:
            return c.numero
    return None


def display_name_expr(prefix: str = ""):
    """
    Equivalente en SQL de `display_name` (sin el placeholder "Médico #id"),
    para ordenar y buscar. `prefix` apunta a un médico relacionado ("medico__").
    """
    propio = Trim(
        Replace(
            Concat(
                Coalesce(F(f"{prefix}nombre"), Value("")), Value(" "),
                Coalesce(F(f"{prefix}paterno"), Value("")), Value(" "),
                Coalesce(F(f"{prefix}materno"), Value("")),
                output_field=CharField(),
            ),
            Value("  "),
            Value(" "),
        )
    )
    return Coalesce(
        NullIf(F(f"{prefix}id_usuario__detalle__nombre_completo"), Value("")),
        NullIf(propio, Value("")),
        NullIf(F(f"{prefix}id_usuario__usuario"), Value("")),
        output_field=CharField(),
    )


def annotate_display_name(qs, prefix: str = "", alias: str = "medico_nombre"):
    """Anota `alias` con el nombre a mostrar (ver `display_name_expr`)."""
    return qs.annotate(**{alias: display_name_expr(prefix)})
