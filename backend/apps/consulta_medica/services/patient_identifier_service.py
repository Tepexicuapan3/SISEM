"""
Identificadores del paciente (cns_identificador_paciente, documento "Historia
Clinica Unificada" 5.1). Es el UNICO punto de entrada para dar de alta, dar de
baja o buscar identificadores: cada alta y cada baja queda en la bitacora de
cambios con su motivo.

Regla de oro: pk_num y cd_familiar nunca se usan uno por el otro. Toda
busqueda resuelve el identificador y termina en el paciente (id_paciente).
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.consulta_medica.models import ChangeLog, Patient, PatientIdentifier
from apps.consulta_medica.services.change_log_service import build_key, record_change, user_text

IdType = PatientIdentifier.IdType
_TABLE = "cns_identificador_paciente"


class IdentifierConflict(Exception):
    """El numero ya es identificador vigente de OTRO paciente."""

    def __init__(self, id_type: str, value: str, owner: Patient):
        super().__init__(
            f"{id_type} {value} ya identifica al paciente {owner.pk} (expediente {owner.no_exp})."
        )
        self.id_type = id_type
        self.value = value
        self.owner = owner


def _clean(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("Un identificador no puede estar vacio.")
    return text[:40]


def find_patient(id_type: str, value: Any) -> Patient | None:
    """Paciente con ese identificador vigente, o None."""
    identifier = (
        PatientIdentifier.objects.select_related("patient")
        .filter(id_type=id_type, value=_clean(value), status=PatientIdentifier.Status.ACTIVE)
        .first()
    )
    return identifier.patient if identifier else None


def register_identifier(
    patient: Patient, id_type: str, value: Any, *, reason: str, user: Any,
) -> tuple[PatientIdentifier, bool]:
    """
    Da de alta el identificador para ``patient``. Devuelve (identificador, creado).
    Si ya lo tiene, no hace nada. Si es de otro paciente, lanza IdentifierConflict:
    nunca se reasigna un numero sin una decision explicita (fusion o correccion).
    """
    if id_type not in IdType.values:
        raise ValueError(f"Tipo de identificador invalido: {id_type!r}.")
    value = _clean(value)

    with transaction.atomic():
        existing = (
            PatientIdentifier.objects.select_for_update().select_related("patient")
            .filter(id_type=id_type, value=value, status=PatientIdentifier.Status.ACTIVE)
            .first()
        )
        if existing:
            if existing.patient_id == patient.pk:
                return existing, False
            raise IdentifierConflict(id_type, value, existing.patient)

        identifier = PatientIdentifier.objects.create(
            patient=patient, id_type=id_type, value=value, created_by=user_text(user),
        )
        record_change(
            table=_TABLE, key=build_key(id_type, value), action=ChangeLog.Action.CREATE,
            reason=reason, user=user, new={"id_paciente": patient.pk},
        )
    return identifier, True


def retire_identifier(identifier: PatientIdentifier, *, reason: str, user: Any) -> bool:
    """Da de baja (sw_status B) sin borrar: queda como evidencia. False si ya estaba de baja."""
    if identifier.status == PatientIdentifier.Status.RETIRED:
        return False
    with transaction.atomic():
        identifier.status = PatientIdentifier.Status.RETIRED
        identifier.updated_by = user_text(user)
        identifier.save(update_fields=["status", "updated_by", "updated_at"])
        record_change(
            table=_TABLE, key=build_key(identifier.id_type, identifier.value),
            action=ChangeLog.Action.DELETE, reason=reason, user=user,
            previous={"id_paciente": identifier.patient_id, "sw_status": PatientIdentifier.Status.ACTIVE},
        )
    return True


def identifiers_from_columns(patient: Patient, *, include_family: bool = True) -> list[tuple[str, str]]:
    """
    Identificadores que corresponden a las columnas de cns_paciente:
    titular (pk_num 0) -> NO_EXP; familiar -> PK_NUM y/o CD_FAMILIAR;
    recien nacido provisional -> PROVISIONAL.
    """
    if patient.pk_num == 0:
        return [(IdType.NO_EXP, str(patient.no_exp))]
    if not include_family:
        return []
    result = []
    if patient.pk_num is not None:
        result.append((IdType.PK_NUM, str(patient.pk_num)))
    if patient.legacy_family_code is not None:
        result.append((IdType.CD_FAMILIAR, str(patient.legacy_family_code)))
    if patient.provisional_code is not None:
        result.append((IdType.PROVISIONAL, str(patient.provisional_code)))
    return result


def register_column_identifiers(
    patient: Patient, *, reason: str, user: Any, include_family: bool = True,
) -> list[tuple[PatientIdentifier, bool]]:
    """Registra los identificadores de identifiers_from_columns(patient)."""
    return [
        register_identifier(patient, id_type, value, reason=reason, user=user)
        for id_type, value in identifiers_from_columns(patient, include_family=include_family)
    ]
