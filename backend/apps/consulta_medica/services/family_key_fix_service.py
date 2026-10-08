"""
Correccion del bug CD_FAMILIAR (documento "Historia Clinica Unificada", 5.1 y 8).

Los comandos migrar_*_legacy guardaron el tp_paciente del legado (que es
cat_familiar.cd_familiar) como si fuera el PK_NUM de SERMED. Las alergias y otros
registros migrados no tienen marca de origen, asi que la correccion se decide por
LLAVE de paciente (no_exp, pk_num), no fila por fila.

Clasificacion de cada llave (no_exp, X), con X distinto de 0, segun el cat_familiar
del legado para ese titular:

  NATIVE          X es PK_NUM de un familiar del titular (y no es cd_familiar): ya
                  esta bien. Solo se registra su identificador PK_NUM.
  LEGACY_TO_PK    X es cd_familiar con PK_NUM traducible P: se mueve todo a (no_exp, P).
  LEGACY_NO_PK    X es cd_familiar sin PK_NUM (NULL o 0): el paciente queda con
                  pk_num NULL y cd_familiar X; los registros conservan X como llave
                  hasta que las tablas apunten a id_paciente.
  AMBIGUOUS       X es cd_familiar de uno y PK_NUM de otro familiar del mismo titular.
  AMBIGUOUS_MAP   el PK_NUM de ese cd_familiar esta repetido en el legado.
  OTHER_TITULAR   X es cd_familiar, pero de un familiar de OTRO titular.
  UNKNOWN         X no aparece en el cat_familiar del legado.
  MERGE_NEEDED    la llave destino ya existe en SIRES: hace falta fusionar pacientes.

Solo se corrigen NATIVE, LEGACY_TO_PK y LEGACY_NO_PK. Todo lo demas va al reporte
para revision humana: nunca se adivina una identidad.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps
from django.db import transaction

from apps.consulta_medica.models import ChangeLog, ClinicalHistory, Patient, PatientIdentifier, StomatologyHistory
from apps.consulta_medica.services.change_log_service import PROCESS_MIGRATION, build_key, record_change
from apps.consulta_medica.services.legacy_family_map import LegacyFamilyMap
from apps.consulta_medica.services.patient_identifier_service import IdentifierConflict, register_identifier

NATIVE = "NATIVE"
LEGACY_TO_PK = "LEGACY_TO_PK"
LEGACY_NO_PK = "LEGACY_NO_PK"
AMBIGUOUS = "AMBIGUOUS"
AMBIGUOUS_MAP = "AMBIGUOUS_MAP"
OTHER_TITULAR = "OTHER_TITULAR"
UNKNOWN = "UNKNOWN"
MERGE_NEEDED = "MERGE_NEEDED"
CONFLICT = "CONFLICT"

FIXABLE = {NATIVE, LEGACY_TO_PK, LEGACY_NO_PK}

# Tablas donde la llave del paciente es unica: si el destino ya existe, hay que fusionar.
_PATIENT_UNIQUE_MODELS = (Patient, ClinicalHistory, StomatologyHistory)


def keyed_models():
    """Modelos de consulta_medica con llave de paciente (no_exp, pk_num): los
    unicos que escribieron los comandos migrar_*_legacy."""
    result = []
    for model in apps.get_app_config("consulta_medica").get_models():
        names = {f.name for f in model._meta.concrete_fields}
        if {"no_exp", "pk_num"} <= names:
            result.append(model)
    return result


def existing_keys() -> set[tuple[str, int]]:
    """Llaves de familiar (pk_num distinto de 0) presentes en SIRES."""
    keys: set[tuple[str, int]] = set()
    for model in keyed_models():
        keys.update(
            model.objects.exclude(pk_num=0).exclude(pk_num__isnull=True)
            .values_list("no_exp", "pk_num").distinct()
        )
    return keys


@dataclass
class KeyDecision:
    no_exp: str
    value: int
    kind: str
    target_pk: int | None = None
    detail: str = ""


def classify(no_exp: str, value: int, fmap: LegacyFamilyMap) -> KeyDecision:
    no_exp = str(no_exp).strip()
    is_cd = value in fmap.cds_by_titular.get(no_exp, set())
    is_pk = value in fmap.pks_by_titular.get(no_exp, set())

    if is_cd and is_pk:
        return KeyDecision(no_exp, value, AMBIGUOUS,
                           detail="Es cd_familiar de un familiar y PK_NUM de otro del mismo titular.")
    if is_pk:
        return KeyDecision(no_exp, value, NATIVE)
    if is_cd:
        if value in fmap.ambiguous_cds:
            return KeyDecision(no_exp, value, AMBIGUOUS_MAP,
                               detail="El PK_NUM de este cd_familiar esta repetido en el legado.")
        target = fmap.pk_by_cd.get(value)
        if target:
            return KeyDecision(no_exp, value, LEGACY_TO_PK, target_pk=target)
        return KeyDecision(no_exp, value, LEGACY_NO_PK, detail="Familiar sin PK_NUM en el legado.")
    if value in fmap.titular_by_cd:
        return KeyDecision(no_exp, value, OTHER_TITULAR,
                           detail=f"cd_familiar del titular {fmap.titular_by_cd[value]}.")
    return KeyDecision(no_exp, value, UNKNOWN, detail="No aparece en el cat_familiar del legado.")


def _merge_blocker(no_exp: str, pk_num: int) -> str | None:
    for model in _PATIENT_UNIQUE_MODELS:
        if model.objects.filter(no_exp=no_exp, pk_num=pk_num).exists():
            return f"Ya existe {model._meta.db_table} con no_exp={no_exp}, pk_num={pk_num}."
    return None


def _cd_owner(cd: int, *, exclude_pk=None) -> Patient | None:
    qs = Patient.objects.filter(legacy_family_code=cd)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.first()


def check(decision: KeyDecision) -> KeyDecision:
    """Revisa, sin escribir, si una llave corregible choca con lo que ya hay en SIRES."""
    if decision.kind == LEGACY_TO_PK:
        blocker = _merge_blocker(decision.no_exp, decision.target_pk)
        if blocker:
            return KeyDecision(decision.no_exp, decision.value, MERGE_NEEDED,
                               target_pk=decision.target_pk, detail=blocker)
    if decision.kind in (LEGACY_TO_PK, LEGACY_NO_PK):
        current = Patient.objects.filter(no_exp=decision.no_exp, pk_num=decision.value).first()
        owner = _cd_owner(decision.value, exclude_pk=current.pk if current else None)
        if owner and not (decision.kind == LEGACY_NO_PK and owner.no_exp == decision.no_exp and owner.pk_num is None):
            return KeyDecision(decision.no_exp, decision.value, MERGE_NEEDED, target_pk=decision.target_pk,
                               detail=f"El cd_familiar {decision.value} ya es del paciente {owner.pk}.")
    return decision


def _log_patient(patient: Patient, previous: dict, created: bool) -> None:
    new = {"pk_num": patient.pk_num, "cd_familiar": patient.legacy_family_code}
    record_change(
        table="cns_paciente", key=build_key("id_paciente", patient.pk),
        action=ChangeLog.Action.CREATE if created else ChangeLog.Action.UPDATE,
        reason=ChangeLog.Reason.LEGACY_KEY_FIX, user=PROCESS_MIGRATION,
        previous=previous, new=new,
    )


def _register(patient: Patient, id_type: str, value) -> None:
    register_identifier(patient, id_type, value, reason=ChangeLog.Reason.MIGRATION, user=PROCESS_MIGRATION)


def apply(decision: KeyDecision) -> dict[str, int]:
    """
    Aplica una llave corregible en una sola transaccion. Devuelve las filas
    movidas por tabla. Lanza IdentifierConflict si un identificador ya es de otro
    paciente (la transaccion se revierte entera).
    """
    moved: dict[str, int] = {}
    no_exp, value = decision.no_exp, decision.value
    IdType = PatientIdentifier.IdType

    with transaction.atomic():
        if decision.kind == NATIVE:
            patient = Patient.objects.filter(no_exp=no_exp, pk_num=value).first()
            if patient:
                _register(patient, IdType.PK_NUM, value)
            return moved

        if decision.kind == LEGACY_TO_PK:
            target = decision.target_pk
            patient = Patient.objects.filter(no_exp=no_exp, pk_num=value).first()
            previous = {"pk_num": value, "cd_familiar": patient.legacy_family_code if patient else None}
            for model in keyed_models():
                count = model.objects.filter(no_exp=no_exp, pk_num=value).update(pk_num=target)
                if count:
                    moved[model._meta.db_table] = count
            patient = Patient.objects.filter(no_exp=no_exp, pk_num=target).first()
            created = patient is None
            if created:
                patient = Patient.objects.create(no_exp=no_exp, pk_num=target, legacy_family_code=value)
            else:
                patient.legacy_family_code = value
                patient.save(update_fields=["legacy_family_code", "updated_at"])
            _log_patient(patient, {} if created else previous, created)
            _register(patient, IdType.PK_NUM, target)
            _register(patient, IdType.CD_FAMILIAR, value)
            return moved

        if decision.kind == LEGACY_NO_PK:
            patient = (
                Patient.objects.filter(no_exp=no_exp, pk_num=value).first()
                or Patient.objects.filter(no_exp=no_exp, pk_num__isnull=True, legacy_family_code=value).first()
            )
            created = patient is None
            if created:
                patient = Patient.objects.create(no_exp=no_exp, pk_num=None, legacy_family_code=value)
                _log_patient(patient, {}, True)
            elif patient.pk_num is not None or patient.legacy_family_code != value:
                previous = {"pk_num": patient.pk_num, "cd_familiar": patient.legacy_family_code}
                patient.pk_num = None
                patient.legacy_family_code = value
                patient.save(update_fields=["pk_num", "legacy_family_code", "updated_at"])
                _log_patient(patient, previous, False)
            _register(patient, IdType.CD_FAMILIAR, value)
            return moved

    raise ValueError(f"La llave {no_exp}/{value} ({decision.kind}) no se corrige automaticamente.")


def run_fix(fmap: LegacyFamilyMap, *, dry_run: bool = False, progress=None) -> dict:
    """
    Clasifica todas las llaves de familiar presentes en SIRES y corrige las que
    se pueden. Devuelve {"counts": {tipo: n}, "moved": {tabla: n}, "review": [KeyDecision]}.
    """
    counts: dict[str, int] = {}
    moved_total: dict[str, int] = {}
    review: list[KeyDecision] = []

    keys = sorted(existing_keys())
    # Primero lo que mueve llaves, despues los que ya estaban bien.
    decisions = [classify(no_exp, value, fmap) for no_exp, value in keys]
    decisions.sort(key=lambda d: 0 if d.kind != NATIVE else 1)

    for index, decision in enumerate(decisions, start=1):
        # Se revisa justo antes de aplicar: cada correccion cambia lo que hay en SIRES.
        decision = check(decision)
        if decision.kind in FIXABLE and not dry_run:
            try:
                for table, count in apply(decision).items():
                    moved_total[table] = moved_total.get(table, 0) + count
            except IdentifierConflict as exc:
                decision = KeyDecision(decision.no_exp, decision.value, CONFLICT,
                                       target_pk=decision.target_pk, detail=str(exc))
        counts[decision.kind] = counts.get(decision.kind, 0) + 1
        if decision.kind not in FIXABLE:
            review.append(decision)
        if progress and index % 500 == 0:
            progress(index, len(decisions))

    return {"counts": counts, "moved": moved_total, "review": review}
