"""
Control del plan de migracion legacy (documento "Historia Clinica Unificada",
seccion 8): bitacora de quien corre cada comando y resolucion de conflictos
en la ficha del paciente entre his_clinica, his_clinicad y SIRES.

Regla por campo de la ficha (catalogos, telefono):
  1. El legado trae vacio              -> nunca borra lo que hay.
  2. La ficha esta vacia y nadie la    -> se aplica el legado.
     toco (sin origen registrado)
  3. El valor actual no es el que dejo -> lo edito SIRES: se conserva SIEMPRE
     el legado (u otro origen)            y se registra el conflicto.
  4. El valor actual vino del legado   -> gana el fe_hisclin mas reciente
                                          (empate o sin fecha: se conserva el
                                          previo) y se registra el conflicto.
"""
import contextlib
import getpass
import socket

from django.utils import timezone

from apps.consulta_medica.models import (
    LegacyMigrationConflict,
    LegacyMigrationRun,
    PatientLegacySource,
)


def _operator(explicit):
    if explicit:
        return explicit[:100]
    try:
        return getpass.getuser()[:100]
    except Exception:  # noqa: BLE001 -- getuser falla sin variables de entorno de usuario
        return "desconocido"


@contextlib.contextmanager
def track_run(command, *, options, operator=None):
    """Registra la ejecucion en cns_bitacora_migracion. Si el comando revienta,
    la fila queda como Fallida con el error y la excepcion se propaga."""
    safe_options = {
        key: value for key, value in options.items()
        if key not in {"password", "stdout", "stderr", "skip_checks"} and value not in (None, False)
    }
    run = LegacyMigrationRun.objects.create(
        command=command[:80],
        operator=_operator(operator),
        host=socket.gethostname()[:100],
        options=", ".join(f"{key}={value}" for key, value in sorted(safe_options.items())) or None,
        dry_run=bool(options.get("dry_run")),
    )
    try:
        yield run
    except BaseException as exc:
        run.status = LegacyMigrationRun.Status.FAILED
        run.summary = f"{type(exc).__name__}: {exc}"[:4000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "summary", "finished_at"])
        raise
    run.status = LegacyMigrationRun.Status.OK
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "rows_read", "summary", "finished_at"])


def _as_text(value):
    return None if value is None else str(value)[:255]


def apply_patient_fields(patient, values, *, legacy_ref, legacy_date, run=None):
    """Aplica `values` ({campo del modelo Patient: valor}) segun la regla del
    modulo. Guarda el paciente si algo cambio. Devuelve los conflictos creados."""
    sources = {source.field: source for source in PatientLegacySource.objects.filter(patient=patient)}
    changed, conflicts = [], []

    def remember(field, value):
        PatientLegacySource.objects.update_or_create(
            patient=patient, field=field,
            defaults={"value": value, "legacy_ref": legacy_ref, "legacy_date": legacy_date},
        )

    def conflict(field, kept, discarded, winner):
        conflicts.append(LegacyMigrationConflict.objects.create(
            run=run, no_exp=patient.no_exp, pk_num=patient.pk_num, field=field,
            kept_value=kept, discarded_value=discarded, legacy_ref=legacy_ref,
            legacy_date=legacy_date, winner=winner,
        ))

    for field, raw in values.items():
        incoming = _as_text(raw)
        if incoming is None or not incoming.strip():
            continue
        current = _as_text(getattr(patient, field))
        source = sources.get(field)

        if source is not None and source.value != current:
            # Regla 3: SIRES lo edito despues de la migracion.
            if current != incoming:
                conflict(field, current, incoming, LegacyMigrationConflict.Winner.SIRES)
            continue
        if source is None and current is not None and current != incoming:
            # Regla 3: valor previo que no vino del legado.
            conflict(field, current, incoming, LegacyMigrationConflict.Winner.SIRES)
            continue
        if current == incoming:
            if source is None or _is_newer(legacy_date, source.legacy_date):
                remember(field, incoming)
            continue
        if source is None:
            # Regla 2.
            setattr(patient, field, raw)
            changed.append(field)
            remember(field, incoming)
            continue
        # Regla 4: dos filas del legado discrepan.
        if _is_newer(legacy_date, source.legacy_date):
            conflict(field, incoming, current, LegacyMigrationConflict.Winner.LEGACY_NEWER)
            setattr(patient, field, raw)
            changed.append(field)
            remember(field, incoming)
        else:
            conflict(field, current, incoming, LegacyMigrationConflict.Winner.PREVIOUS_LEGACY)

    if changed:
        patient.save(update_fields=changed)
    return conflicts


def _is_newer(candidate, previous):
    if candidate is None:
        return False
    return previous is None or candidate > previous
