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
    ChangeLog,
    DentalTreatment,
    FamilyHistory,
    Habit,
    PersonalHistory,
    Presence,
    SpecialtySource,
    SurgicalHistory,
)
from apps.consulta_medica.services.change_log_service import (
    PROCESS_SIRES,
    build_key,
    deactivation_reason,
    edit_reason,
    record_change,
)
from apps.consulta_medica.services.diagnosis_redaction_service import redact_cie_if_restricted
from apps.consulta_medica.services.patient_link_service import for_patient
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

from apps.consulta_medica.services.paciente_entrada import llave_publica
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
    if not Visit.objects.filter(id_visit=visit_id, patient__no_exp=normalizar_no_exp(no_exp)).exists():
        raise _validation_error("visitId", "La visita no existe o no es de este paciente.")
    return visit_id


def _blank_to_none(value, _no_exp):
    if isinstance(value, str):
        value = value.strip()
    return value or None


# ── Contratos ────────────────────────────────────────────────────────────────

def _base_contract(record):
    return {
        "noExp": llave_publica(record)[0],
        "pkNum": llave_publica(record)[1],
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
        "presence": record.presence,
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
        "presence": record.presence,
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
        # Anios (documento 5.2), no fechas.
        "since": record.since,
        "until": record.until,
        "status": record.status,
        "recordStatus": record.record_status,
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
    # Reglas entre campos sobre el registro YA armado (alta o edicion parcial):
    # lanza VisitDomainError si la combinacion no tiene sentido clinico.
    validate: Callable | None = None
    # Registro con historial (documento 5.2, HABITO): una fila vigente por
    # paciente y por este campo; editar crea una version nueva y la anterior
    # pasa a B. None = se edita en su lugar.
    versioned_by: str | None = None
    # Tabla para cns_bitacora_cambios (documento 5.2: modificaciones y bajas
    # siempre se registran). "" = fuera de la 5.2, no se registra aqui.
    table: str = ""


# ── Reglas de "lo niega" (sw_presente = N, documento 5.2) ────────────────────

def _validate_personal(record):
    if record.presence == Presence.DENIED and record.diagnosis_date:
        raise _validation_error("diagnosisDate", "Si el paciente lo niega, no lleva fecha de diagnostico.")


def _validate_family(record):
    if record.presence != Presence.DENIED:
        return
    if record.is_deceased or record.cause_of_death:
        raise _validation_error("isDeceased", "Si lo niega, no se registra finado ni causa de muerte.")
    if not record.cie_id and not record.description:
        raise _validation_error("description", "Indica que padecimiento niega (CIE-10 o descripcion).")


PERSONAL_HISTORY = RecordSpec(
    model=PersonalHistory,
    audit_name="PersonalHistory",
    fields={
        "cieCode": ("cie_id", _resolve_cie),
        "description": ("description", _blank_to_none),
        "presence": ("presence", _blank_to_none),
        "diagnosisDate": ("diagnosis_date", _blank_to_none),
        "status": ("status", _blank_to_none),
    },
    contract=_personal_contract,
    select_related=("cie",),
    validate=_validate_personal,
    table="cns_antecedente_personal",
)

FAMILY_HISTORY = RecordSpec(
    model=FamilyHistory,
    audit_name="FamilyHistory",
    fields={
        "relationshipId": ("relationship_id", _resolve_relationship),
        "cieCode": ("cie_id", _resolve_cie),
        "description": ("description", _blank_to_none),
        "presence": ("presence", _blank_to_none),
        "isDeceased": ("is_deceased", lambda value, _n: bool(value)),
        "causeOfDeath": ("cause_of_death", _blank_to_none),
    },
    contract=_family_contract,
    select_related=("cie", "relationship"),
    validate=_validate_family,
    table="cns_antecedente_familiar",
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
    table="cns_antecedente_quirurgico",
)

def _validate_habit(record):
    this_year = timezone.localdate().year
    for field in ("since", "until"):
        year = getattr(record, field)
        if year is not None and not 1900 <= year <= this_year:
            raise _validation_error(field, f"Anio invalido: entre 1900 y {this_year}.")
    if record.status == Habit.Status.DENIED and any(
        (record.frequency, record.quantity, record.since, record.until)
    ):
        raise _validation_error("status", "Si lo niega, no lleva frecuencia, cantidad ni anios.")
    if record.until is not None and record.status != Habit.Status.FORMER:
        raise _validation_error("until", "El anio en que lo dejo solo va con el estado 'lo dejo'.")
    if record.since is not None and record.until is not None and record.until < record.since:
        raise _validation_error("until", "Lo dejo antes de empezar: revisa los anios.")


HABIT = RecordSpec(
    model=Habit,
    audit_name="Habit",
    fields={
        "habitId": ("habit_id", _resolve_habit),
        "frequency": ("frequency", _blank_to_none),
        "quantity": ("quantity", _blank_to_none),
        "since": ("since", _blank_to_none),
        "until": ("until", _blank_to_none),
        "status": ("status", _blank_to_none),
        "notes": ("notes", _blank_to_none),
    },
    contract=_habit_contract,
    select_related=("habit",),
    validate=_validate_habit,
    versioned_by="habit_id",
    table="cns_habito",
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


def _active_queryset(spec, no_exp, pk_num):
    """Registros vivos del paciente; en los versionados, solo la version vigente."""
    queryset = spec.model.objects.select_related(*spec.select_related).filter(is_active=True)
    if spec.versioned_by:
        queryset = queryset.filter(record_status="A")
    return for_patient(queryset, no_exp, pk_num)


def _get_active(spec, no_exp, pk_num, record_id):
    record = _active_queryset(spec, no_exp, pk_num).filter(pk=record_id).first()
    if record is None:
        raise VisitDomainError("RECORD_NOT_FOUND", "Registro no encontrado.", 404)
    return record


def _previous_versions(spec, no_exp, pk_num, permissions, roles):
    """Versiones anteriores (B) por valor de `versioned_by`, la mas reciente primero."""
    previous = for_patient(
        spec.model.objects.select_related(*spec.select_related).filter(is_active=True, record_status="B"),
        no_exp, pk_num,
    ).order_by("-created_at", "-pk")
    grouped = {}
    for record in previous:
        grouped.setdefault(getattr(record, spec.versioned_by), []).append(
            spec.contract(record, permissions, roles)
        )
    return grouped


def list_records(spec, no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    records = _active_queryset(spec, no_exp, pk_num).order_by(*spec.ordering)
    items = [spec.contract(record, permissions, roles) for record in records]
    if spec.versioned_by:
        history = _previous_versions(spec, no_exp, pk_num, permissions, roles)
        for record, item in zip(records, items):
            item["history"] = history.get(getattr(record, spec.versioned_by), [])
    return {"items": items, "restrictedCount": sum(1 for item in items if item.get("isRestricted"))}


def _ensure_no_current_version(spec, no_exp, pk_num, values):
    key_value = values.get(spec.versioned_by)
    if key_value is None:
        return
    if _active_queryset(spec, no_exp, pk_num).filter(**{spec.versioned_by: key_value}).exists():
        camel = next(camel for camel, (field, _r) in spec.fields.items() if field == spec.versioned_by)
        raise VisitDomainError(
            "RECORD_ALREADY_CURRENT",
            "Ya hay un registro vigente de este tipo: editalo en lugar de agregar otro.",
            409,
            details={camel: ["Ya hay un registro vigente de este tipo: editalo en lugar de agregar otro."]},
        )


def create_record(spec, no_exp, pk_num, roles, validated_data, actor_id, permissions=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)
    values = _model_fields(spec, validated_data, no_exp)
    source = validated_data.get("source") or SpecialtySource.GENERAL

    record = spec.model(
        no_exp=no_exp, pk_num=pk_num, source=source,
        created_by_id=actor_id, updated_by_id=actor_id, **values,
    )
    if spec.validate:
        spec.validate(record)
    if spec.versioned_by:
        _ensure_no_current_version(spec, no_exp, pk_num, values)

    with transaction.atomic():
        record.save()
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


def _update_versioned(spec, no_exp, pk_num, record, values, validated_data, actor_id, permissions, roles,
                      *, audit_hook):
    """HABITO: la vigente pasa a B y se crea la version nueva con los cambios;
    el porque va a la bitacora de cambios (ACTUALIZACION)."""
    key = spec.versioned_by
    if key in values and values[key] != getattr(record, key):
        raise _validation_error(
            next(camel for camel, (field, _r) in spec.fields.items() if field == key),
            "No se cambia el tipo: da de baja este registro y agrega el nuevo.",
        )

    editable = [field for field, _resolver in spec.fields.values()]
    previous = {field: getattr(record, field) for field in editable}
    current = {**previous, **values}
    if current == previous:
        return spec.contract(record, permissions, roles)

    new_version = spec.model(
        no_exp=llave_publica(record)[0], pk_num=llave_publica(record)[1], patient_id=record.patient_id,
        source=validated_data.get("source") or record.source,
        created_by_id=actor_id, updated_by_id=actor_id, **current,
    )
    if spec.validate:
        spec.validate(new_version)

    reason = (validated_data.get("reason") or "").strip()
    with transaction.atomic():
        datos_antes = _snapshot(record, spec)
        record.record_status = "B"
        record.updated_by_id = actor_id
        record.save(update_fields=["record_status", "updated_by_id", "updated_at"])
        new_version.save()

        record_change(
            table=spec.table,
            key=build_key(spec.model._meta.pk.column, record.pk),
            action=ChangeLog.Action.UPDATE,
            reason=ChangeLog.Reason.CLINICAL_UPDATE,
            user=actor_id if actor_id is not None else PROCESS_SIRES,
            previous=previous,
            new={**current, "id_version_nueva": new_version.pk, **({"motivo": reason[:500]} if reason else {})},
        )
        datos_despues = _snapshot(new_version, spec)
        datos_despues["changedFields"] = sorted(
            camel for camel in datos_despues if datos_antes.get(camel) != datos_despues[camel]
        )
        datos_despues["previousVersionId"] = record.pk
        audit_hook(
            action=f"{spec.audit_name}Updated",
            resource_id=new_version.pk,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
        )

    return spec.contract(_get_active(spec, no_exp, pk_num, new_version.pk), permissions, roles)


def update_record(spec, no_exp, pk_num, record_id, roles, validated_data, actor_id, permissions=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)
    record = _get_active(spec, no_exp, pk_num, record_id)
    values = _model_fields(spec, validated_data, no_exp)

    if spec.versioned_by:
        return _update_versioned(
            spec, no_exp, pk_num, record, values, validated_data, actor_id, permissions, roles,
            audit_hook=audit_hook,
        )

    datos_antes = _snapshot(record, spec)
    editable = [field for field, _resolver in spec.fields.values()]
    previous = {field: getattr(record, field) for field in editable}
    was_done = getattr(record, "status", None) == DentalTreatment.Status.DONE
    for field_name, value in values.items():
        setattr(record, field_name, value)
    # La edicion es parcial: la regla se evalua sobre el registro completo.
    if spec.validate:
        spec.validate(record)

    with transaction.atomic():
        record.updated_by_id = actor_id
        if spec is DENTAL_TREATMENT and record.status == DentalTreatment.Status.DONE and not was_done:
            record.performed_at = timezone.now()
        record.save()

        if spec.table:
            current = {field: getattr(record, field) for field in editable}
            # record_change no escribe nada si no cambio ningun campo.
            record_change(
                table=spec.table,
                key=build_key(spec.model._meta.pk.column, record.pk),
                action=ChangeLog.Action.UPDATE,
                reason=edit_reason(previous, current, evolution_fields=("status",)),
                user=actor_id if actor_id is not None else PROCESS_SIRES,
                previous=previous,
                new=current,
            )

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
        if spec.table:
            record_change(
                table=spec.table,
                key=build_key(spec.model._meta.pk.column, record.pk),
                action=ChangeLog.Action.DELETE,
                reason=deactivation_reason(record.deletion_reason),
                user=actor_id if actor_id is not None else PROCESS_SIRES,
                previous={
                    "is_active": True,
                    **{field: getattr(record, field) for field, _resolver in spec.fields.values()},
                },
            )
        audit_hook(
            action=f"{spec.audit_name}Deactivated",
            resource_id=record.pk,
            datos_antes={"isActive": True},
            datos_despues={"isActive": False, "reason": record.deletion_reason},
        )

    return {"id": record.pk, "isActive": False}
