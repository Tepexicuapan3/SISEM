"""
Escritura de la bitacora de cambios (cns_bitacora_cambios, documento "Historia
Clinica Unificada" seccion 6). Es el UNICO punto de entrada: ningun otro codigo
crea filas de ChangeLog directamente.

Uso tipico:
    antes = snapshot(paciente, ["ds_nombre", "fe_nacimiento"])
    ... modificar y guardar paciente ...
    record_change(
        table="cns_paciente", key=build_key("id_paciente", paciente.pk),
        action=ChangeLog.Action.UPDATE, reason=ChangeLog.Reason.SERMED_SYNC,
        user=PROCESS_SERMED_SYNC,
        previous=antes, new=snapshot(paciente, ["ds_nombre", "fe_nacimiento"]),
    )

Llamarlo dentro de la misma transaccion que el cambio, para que no quede un
cambio sin bitacora ni una bitacora sin cambio.
"""

from __future__ import annotations

from typing import Any, Iterable

from apps.consulta_medica.models import ChangeLog

# Usuario de la bitacora cuando el cambio lo hace un proceso y no una persona.
PROCESS_SERMED_SYNC = "SYNC_SERMED"
PROCESS_MIGRATION = "MIGRACION"
# Alta automatica desde SIRES sin usuario conocido (p. ej. al abrir la historia).
PROCESS_SIRES = "SIRES"


def build_key(*parts: Any) -> str:
    """Llave legible del registro: build_key("PK_NUM", 88731) -> "PK_NUM|88731"."""
    if not parts:
        raise ValueError("La llave de la bitacora necesita al menos un componente.")
    return "|".join(str(part) for part in parts)[:80]


def snapshot(instance: Any, fields: Iterable[str]) -> dict[str, Any]:
    """Valores actuales de ``fields`` en ``instance`` (para pasar como previous/new).
    Para una FK usar el nombre con _id (p. ej. "occupation_id")."""
    return {field: getattr(instance, field) for field in fields}


def changed_values(
    previous: dict[str, Any] | None, new: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Solo las columnas que cambiaron, como (anterior, nuevo)."""
    previous, new = previous or {}, new or {}
    keys = [key for key in {**previous, **new} if previous.get(key) != new.get(key)]
    return {key: previous.get(key) for key in keys}, {key: new.get(key) for key in keys}


def user_text(user: Any) -> str:
    """Acepta un SyUsuario, su id o el nombre de un proceso."""
    if user is None or user == "":
        raise ValueError("La bitacora necesita usuario o proceso: nunca se registra un cambio anonimo.")
    value = getattr(user, "pk", user)
    return str(value)[:40]


def edit_reason(previous: dict[str, Any], new: dict[str, Any], *, evolution_fields: Iterable[str]) -> str:
    """Motivo de una edicion de un dato clinico permanente (documento 5.2).

    Si solo cambio el estado clinico (activo -> resuelto...), el dato evoluciono:
    ACTUALIZACION. Si cambio cualquier otra cosa (sustancia, CIE, fecha), se
    corrigio como se capturo: CORRECCION."""
    changed = {key for key in {**previous, **new} if previous.get(key) != new.get(key)}
    if changed and changed <= set(evolution_fields):
        return ChangeLog.Reason.CLINICAL_UPDATE
    return ChangeLog.Reason.CORRECTION


def deactivation_reason(motive: str | None) -> str:
    """Motivo de una baja: "BAJA: <texto del usuario>" (filtrable por prefijo).
    Una baja no guarda valor nuevo; el texto completo queda en la columna de
    motivo del propio registro (motivo_baja)."""
    motive = (motive or "").strip()
    return f"BAJA: {motive}"[:60] if motive else "BAJA"


def record_change(
    *,
    table: str,
    key: str,
    action: str,
    reason: str,
    user: Any,
    previous: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    occurred_at=None,
) -> ChangeLog | None:
    """
    Registra un alta (A), modificacion (M) o baja (B) con su motivo.

    En una modificacion guarda solo las columnas que cambiaron; si no cambio
    nada, no escribe y devuelve None. En un alta no hay valor anterior y en una
    baja no hay valor nuevo.
    """
    if action not in ChangeLog.Action.values:
        raise ValueError(f"Accion de bitacora invalida: {action!r}.")
    if not reason or not reason.strip():
        raise ValueError("La bitacora necesita un motivo: es la razon de existir de esta tabla.")
    if not table or not key:
        raise ValueError("La bitacora necesita tabla y llave del registro.")

    if action == ChangeLog.Action.UPDATE:
        previous, new = changed_values(previous, new)
        if not new and not previous:
            return None
    elif action == ChangeLog.Action.CREATE:
        previous = None
    else:
        new = None

    return ChangeLog.objects.create(
        table=table[:40],
        key=key[:80],
        action=action,
        reason=reason.strip()[:60],
        previous_value=previous or None,
        new_value=new or None,
        user=user_text(user),
        # Por defecto, ahora. Se pasa al registrar un hecho del pasado (p. ej.
        # un conflicto de migracion que ya existia antes de la bitacora).
        **({"occurred_at": occurred_at} if occurred_at is not None else {}),
    )
