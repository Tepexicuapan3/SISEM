"""
Registros permanentes 1:N del paciente de la historia clinica unificada:
antecedentes personales/familiares/quirurgicos, habitos y tratamientos
dentales. Todos comparten el mismo ciclo de vida -- listar, crear, editar,
dar de baja logica CON MOTIVO (nada se borra) -- y cada escritura se audita
en modo estricto (si falla la auditoria se revierte la operacion).

Cada recurso se describe con un `RecordSpec` en vez de repetir el mismo
caso de uso cinco veces.
"""
from dataclasses import dataclass
from typing import Callable

from django.db import transaction
from django.utils import timezone

from apps.catalogos.models import CatCie9Mc, CatCies, CatHabito, CatPiezaDental, Parentesco
from apps.consulta_medica.models import (
    DentalTreatment,
    FamilyHistory,
    Habit,
    PersonalHistory,
    SpecialtySource,
    SurgicalHistory,
)
from apps.consulta_medica.services.diagnosis_redaction_service import redact_cie_if_restricted
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

from .consultation_usecase import ensure_doctor_role


def _validation_error(field, message):
    return VisitDomainError(
        "VALIDATION_ERROR", "Hay errores en el formulario", 422, details={field: [message]},
    )


def _iso(value):
    return value.isoformat() if value else None


# ── Resolutores de FKs (camelCase -> valor del modelo, validado) ─────────────

def _resolve_cie(code, _no_exp):
    code = (code or "").strip().upper()
    if not code:
        return None
    if not CatCies.objects.filter(code=code, is_active=True).exists():
        raise _validation_error("cieCode", "El codigo CIE-10 no existe o no esta activo.")
    return code


def _resolve_cie9(cie9_id, _no_exp):
    if cie9_id is None:
        return None
    if not CatCie9Mc.objects.filter(pk=cie9_id, is_active=True).exists():
        raise _validation_error("procedureCie9Id", "El procedimiento CIE-9-MC no existe o no esta activo.")
    return cie9_id


def _resolve_relationship(relationship_id, _no_exp):
    relationship_id = (relationship_id or "").strip()
    if not relationship_id:
        return None
    if not Parentesco.objects.filter(pk=relationship_id, is_active=True).exists():
        raise _validation_error("relationshipId", "Parentesco invalido.")
    return relationship_id


def _resolve_habit(habit_id, _no_exp):
    if not CatHabito.objects.filter(pk=habit_id, is_active=True).exists():
        raise _validation_error("habitId", "Habito invalido.")
    return habit_id


def _resolve_tooth(tooth_fdi, _no_exp):
    tooth_fdi = (tooth_fdi or "").strip()
    if not tooth_fdi:
        return None
    if not CatPiezaDental.objects.filter(pk=tooth_fdi).exists():
        raise _validation_error("toothFdi", "Numero de pieza FDI invalido.")
    return tooth_fdi


def _resolve_visit(visit_id, no_exp):
    if visit_id is None:
        return None
    if not Visit.objects.filter(id_visit=visit_id, no_exp=no_exp).exists():
        raise _validation_error("visitId", "La visita no existe o no es de este paciente.")
    return visit_id


def _blank_to_none(value, _no_exp):
    if isinstance(value, str):
        value = value.strip()
    return value or None


# ── Contratos ────────────────────────────────────────────────────────────────

def _base_contract(record):
    return {
        "noExp": record.no_exp,
        "pkNum": record.pk_num,
        "source": record.source,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
        "createdById": record.created_by_id,
    }


def _cie_contract(record, permissions, roles=None):
    """Antecedentes con CIE-10 sensible (VIH, salud mental, sustancias) se
    sirven redactados a quien no tiene el permiso -- documento: "los demas
    ven 'antecedente restringido', nunca el diagnostico"."""
    code = record.cie_id
    description = record.cie.description if record.cie_id else None
    code, description, free_text, restricted = redact_cie_if_restricted(
        code=code, description=description, permissions=permissions, roles=roles,
        linked_text=record.description,
    )
    return {
        "cieCode": code,
        "cieDescription": description,
        "description": free_text,
        "isRestricted": restricted,
    }


def _personal_contract(record, permissions, roles=None):
    return {
        "id": record.id_personal_history,
        **_cie_contract(record, permissions, roles),
        "diagnosisDate": _iso(record.diagnosis_date),
        "status": record.status,
        **_base_contract(record),
    }


def _family_contract(record, permissions, roles=None):
    return {
        "id": record.id_family_history,
        "relationshipId": record.relationship_id,
        "relationshipName": record.relationship.name if record.relationship_id else None,
        **_cie_contract(record, permissions, roles),
        "isDeceased": record.is_deceased,
        "causeOfDeath": record.cause_of_death,
        **_base_contract(record),
    }


def _surgical_contract(record, _permissions, _roles=None):
    return {
        "id": record.id_surgical_history,
        "procedure": record.procedure,
        "procedureCie9Id": record.procedure_cie9_id,
        "procedureCie9Code": record.procedure_cie9.code if record.procedure_cie9_id else None,
        "approximateDate": _iso(record.approximate_date),
        "place": record.place,
        **_base_contract(record),
    }


def _habit_contract(record, _permissions, _roles=None):
    return {
        "id": record.id_habit,
        "habitId": record.habit_id,
        "habitCode": record.habit.code,
        "habitName": record.habit.name,
        "frequency": record.frequency,
        "quantity": record.quantity,
        "since": _iso(record.since),
        "status": record.status,
        "notes": record.notes,
        **_base_contract(record),
    }


def _treatment_contract(record, _permissions, _roles=None):
    return {
        "id": record.id_dental_treatment,
        "visitId": record.visit_id,
        "toothFdi": record.tooth_id,
        "procedure": record.procedure,
        "procedureCie9Id": record.procedure_cie9_id,
        "procedureCie9Code": record.procedure_cie9.code if record.procedure_cie9_id else None,
        "status": record.status,
        "performedAt": record.performed_at,
        **_base_contract(record),
    }


@dataclass(frozen=True)
class RecordSpec:
    model: type
    audit_name: str
    # camelCase del serializer -> (campo del modelo, resolutor)
    fields: dict
    contract: Callable
    select_related: tuple = ()
    ordering: tuple = ("created_at",)


PERSONAL_HISTORY = RecordSpec(
    model=PersonalHistory,
    audit_name="PersonalHistory",
    fields={
        "cieCode": ("cie_id", _resolve_cie),
        "description": ("description", _blank_to_none),
        "diagnosisDate": ("diagnosis_date", _blank_to_none),
        "status": ("status", _blank_to_none),
    },
    contract=_personal_contract,
    select_related=("cie",),
)

FAMILY_HISTORY = RecordSpec(
    model=FamilyHistory,
    audit_name="FamilyHistory",
    fields={
        "relationshipId": ("relationship_id", _resolve_relationship),
        "cieCode": ("cie_id", _resolve_cie),
        "description": ("description", _blank_to_none),
        "isDeceased": ("is_deceased", lambda value, _n: bool(value)),
        "causeOfDeath": ("cause_of_death", _blank_to_none),
    },
    contract=_family_contract,
    select_related=("cie", "relationship"),
)

SURGICAL_HISTORY = RecordSpec(
    model=SurgicalHistory,
    audit_name="SurgicalHistory",
    fields={
        "procedure": ("procedure", _blank_to_none),
        "procedureCie9Id": ("procedure_cie9_id", _resolve_cie9),
        "approximateDate": ("approximate_date", _blank_to_none),
        "place": ("place", _blank_to_none),
    },
    contract=_surgical_contract,
    select_related=("procedure_cie9",),
)

HABIT = RecordSpec(
    model=Habit,
    audit_name="Habit",
    fields={
        "habitId": ("habit_id", _resolve_habit),
        "frequency": ("frequency", _blank_to_none),
        "quantity": ("quantity", _blank_to_none),
        "since": ("since", _blank_to_none),
        "status": ("status", _blank_to_none),
        "notes": ("notes", _blank_to_none),
    },
    contract=_habit_contract,
    select_related=("habit",),
)

DENTAL_TREATMENT = RecordSpec(
    model=DentalTreatment,
    audit_name="DentalTreatment",
    fields={
        "visitId": ("visit_id", _resolve_visit),
        "toothFdi": ("tooth_id", _resolve_tooth),
        "procedure": ("procedure", _blank_to_none),
        "procedureCie9Id": ("procedure_cie9_id", _resolve_cie9),
        "status": ("status", _blank_to_none),
    },
    contract=_treatment_contract,
    select_related=("procedure_cie9",),
    ordering=("-created_at",),
)


def _snapshot(record, spec):
    """Estado JSON-safe de los campos editables (auditoria). Textos largos
    (`notes`) como longitud, criterio A3."""
    snapshot = {}
    for camel, (field_name, _resolver) in spec.fields.items():
        value = getattr(record, field_name)
        if field_name == "notes":
            snapshot["notesLen"] = len(value) if value else None
        elif hasattr(value, "isoformat"):
            snapshot[camel] = value.isoformat()
        else:
            snapshot[camel] = value
    return snapshot


def _model_fields(spec, validated_data, no_exp):
    values = {}
    for camel, (field_name, resolver) in spec.fields.items():
        if camel in validated_data:
            values[field_name] = resolver(validated_data[camel], no_exp)
    return values


def _get_active(spec, no_exp, pk_num, record_id):
    record = (
        spec.model.objects.select_related(*spec.select_related)
        .filter(pk=record_id, no_exp=no_exp, pk_num=pk_num, is_active=True)
        .first()
    )
    if record is None:
        raise VisitDomainError("RECORD_NOT_FOUND", "Registro no encontrado.", 404)
    return record


def list_records(spec, no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    records = (
        spec.model.objects.select_related(*spec.select_related)
        .filter(no_exp=no_exp, pk_num=pk_num, is_active=True)
        .order_by(*spec.ordering)
    )
    items = [spec.contract(record, permissions, roles) for record in records]
    return {"items": items, "restrictedCount": sum(1 for item in items if item.get("isRestricted"))}


def create_record(spec, no_exp, pk_num, roles, validated_data, actor_id, permissions=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)
    values = _model_fields(spec, validated_data, no_exp)
    source = validated_data.get("source") or SpecialtySource.GENERAL

    with transaction.atomic():
        record = spec.model.objects.create(
            no_exp=no_exp, pk_num=pk_num, source=source,
            created_by_id=actor_id, updated_by_id=actor_id, **values,
        )
        if spec is DENTAL_TREATMENT and record.status == DentalTreatment.Status.DONE:
            record.performed_at = timezone.now()
            record.save(update_fields=["performed_at"])
        audit_hook(
            action=f"{spec.audit_name}Created",
            resource_id=record.pk,
            datos_antes=None,
            datos_despues=_snapshot(record, spec),
        )

    record = _get_active(spec, no_exp, pk_num, record.pk)
    return spec.contract(record, permissions, roles)


def update_record(spec, no_exp, pk_num, record_id, roles, validated_data, actor_id, permissions=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)
    record = _get_active(spec, no_exp, pk_num, record_id)
    values = _model_fields(spec, validated_data, no_exp)

    with transaction.atomic():
        datos_antes = _snapshot(record, spec)
        was_done = getattr(record, "status", None) == DentalTreatment.Status.DONE
        for field_name, value in values.items():
            setattr(record, field_name, value)
        record.updated_by_id = actor_id
        if spec is DENTAL_TREATMENT and record.status == DentalTreatment.Status.DONE and not was_done:
            record.performed_at = timezone.now()
        record.save()

        datos_despues = _snapshot(record, spec)
        datos_despues["changedFields"] = sorted(
            key for key in datos_despues if datos_antes.get(key) != datos_despues[key]
        )
        audit_hook(
            action=f"{spec.audit_name}Updated",
            resource_id=record.pk,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
        )

    record = _get_active(spec, no_exp, pk_num, record.pk)
    return spec.contract(record, permissions, roles)


def deactivate_record(spec, no_exp, pk_num, record_id, roles, reason, actor_id, permissions=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)
    record = _get_active(spec, no_exp, pk_num, record_id)

    with transaction.atomic():
        record.is_active = False
        record.deletion_reason = reason.strip()
        record.deleted_at = timezone.now()
        record.deleted_by_id = actor_id
        record.updated_by_id = actor_id
        record.save()
        audit_hook(
            action=f"{spec.audit_name}Deactivated",
            resource_id=record.pk,
            datos_antes={"isActive": True},
            datos_despues={"isActive": False, "reason": record.deletion_reason},
        )

    return {"id": record.pk, "isActive": False}
