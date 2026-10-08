"""
Paso 6 del 5.1 (documento "Historia Clinica Unificada"): sincronizacion
SERMED -> PACIENTE. SERMED manda en nombre, fecha de nacimiento, sexo y la
CURP de los titulares; SIRES nunca toca lo que captura (ocupacion, telefono,
CURP de familiares...).

Alcance de esta version: actualiza los pacientes que YA existen en SIRES (se
crean al abrir su historia). No crea pacientes nuevos: asi un recien nacido o
un familiar del legado nunca se duplica antes de que exista la cola de liga.

Regla CURP vs sexo (confirmada 2026-10-07), se reevalua en cada corrida:
  - La CURP de SERMED que no cumple el formato (p. ej. 'SIN CURP') no se carga.
  - Si la fecha de nacimiento de la CURP NO coincide con FE_NAC, la CURP
    probablemente es de otra persona: no se carga y va al reporte.
  - Si la fecha coincide pero el sexo no, gana el sexo de la CURP (la emite
    RENAPO desde el acta) y va al reporte para que Capital Humano corrija.
  - Una CURP que ya es de otro paciente no se carga: candidato a fusion.
Todo lo que la sincronizacion no carga queda en el reporte de discrepancias
para Capital Humano. SIRES nunca escribe en Oracle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from django.db import transaction

from apps.consulta_medica.models import ChangeLog, Patient, PatientIdentifier, PatientSermedState
from apps.consulta_medica.services.change_log_service import (
    PROCESS_SERMED_SYNC,
    build_key,
    record_change,
    snapshot,
)
from apps.consulta_medica.services.curp_rules import (
    birth_date_from_curp,
    normalize_curp,
    sermed_sex_to_sires,
    sex_from_curp,
)
from apps.consulta_medica.services.patient_identifier_service import IdentifierConflict, register_identifier
from apps.consulta_medica.services.sermed_source import ReplicaSermedSource, SermedEmployee, SermedFamilyMember

# Tipos de discrepancia del reporte para Capital Humano.
CURP_INVALIDA = "CURP_INVALIDA"
CURP_FECHA = "CURP_FECHA"
SEXO_DE_CURP = "SEXO_DE_CURP"
CURP_DUPLICADA = "CURP_DUPLICADA"
NO_ENCONTRADO = "NO_ENCONTRADO"
CAMBIO_TITULAR = "CAMBIO_TITULAR"
IDENTIFICADOR_EN_CONFLICTO = "IDENTIFICADOR_EN_CONFLICTO"

_STATE_FIELDS = (
    "found", "holder_no_exp", "relationship_code", "beneficiary_type",
    "valid_until", "leave_date", "leave_code", "clinic_code",
)
_NAME_FIELDS = ("paternal_surname", "maternal_surname", "first_name")


@dataclass
class Discrepancy:
    patient_id: int
    no_exp: str
    pk_num: int | None
    kind: str
    detail: str


@dataclass
class PatientPlan:
    patient: Patient
    fields: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    register_pk_num: bool = False
    discrepancies: list[Discrepancy] = field(default_factory=list)

    def report(self, kind: str, detail: str) -> None:
        p = self.patient
        self.discrepancies.append(Discrepancy(p.pk, p.no_exp, p.pk_num, kind, detail))


def _set_if_changed(plan: PatientPlan, attr: str, value) -> None:
    if value is not None and getattr(plan.patient, attr) != value:
        plan.fields[attr] = value


def _copy_identity(plan: PatientPlan, person) -> None:
    for attr in _NAME_FIELDS:
        _set_if_changed(plan, attr, getattr(person, attr))
    _set_if_changed(plan, "birth_date", person.birth_date)


def plan_employee(patient: Patient, emp: SermedEmployee) -> PatientPlan:
    plan = PatientPlan(patient)
    _copy_identity(plan, emp)

    sex = sermed_sex_to_sires(emp.sex_code)
    curp_to_load = None
    curp = normalize_curp(emp.curp)
    if emp.curp and emp.curp.strip() and curp is None:
        plan.report(CURP_INVALIDA, f"SERMED trae {emp.curp.strip()!r}, que no es una CURP valida.")
    if curp:
        curp_date = birth_date_from_curp(curp)
        owner = Patient.objects.filter(curp=curp).exclude(pk=patient.pk).first()
        if emp.birth_date and curp_date and curp_date != emp.birth_date:
            plan.report(CURP_FECHA, f"La CURP {curp} indica nacimiento {curp_date:%d/%m/%Y} y FE_NAC es "
                                    f"{emp.birth_date:%d/%m/%Y}: no se carga.")
        elif owner:
            plan.report(CURP_DUPLICADA, f"La CURP {curp} ya es del paciente {owner.pk} "
                                        f"(expediente {owner.no_exp}): no se carga.")
        else:
            curp_to_load = curp
            curp_sex = sex_from_curp(curp)
            if sex and curp_sex != sex:
                plan.report(SEXO_DE_CURP, f"CD_SEXO de SERMED es {emp.sex_code!r} y la CURP indica "
                                          f"'{curp_sex}': se toma el de la CURP.")
            sex = curp_sex

    if curp_to_load:
        if patient.curp != curp_to_load or patient.curp_source != Patient.CurpSource.SERMED:
            plan.fields["curp"] = curp_to_load
            plan.fields["curp_source"] = Patient.CurpSource.SERMED
    elif patient.curp_source == Patient.CurpSource.SERMED:
        # Ya no se puede sostener la CURP que se habia cargado de SERMED.
        plan.fields["curp"] = None
        plan.fields["curp_source"] = None
    _set_if_changed(plan, "sex", sex)

    plan.state = {
        "found": True, "holder_no_exp": None, "relationship_code": None, "beneficiary_type": None,
        "valid_until": emp.valid_until, "leave_date": emp.leave_date,
        "leave_code": emp.leave_code, "clinic_code": emp.clinic_code,
    }
    return plan


def plan_family_member(patient: Patient, member: SermedFamilyMember) -> PatientPlan:
    plan = PatientPlan(patient)
    _copy_identity(plan, member)
    if member.holder_no_exp and member.holder_no_exp != str(patient.no_exp):
        plan.report(CAMBIO_TITULAR, f"En SERMED su titular es {member.holder_no_exp}; en SIRES, {patient.no_exp}.")
    plan.register_pk_num = True
    plan.state = {
        "found": True, "holder_no_exp": member.holder_no_exp,
        "relationship_code": member.relationship_code, "beneficiary_type": member.beneficiary_type,
        "valid_until": member.valid_until, "leave_date": None, "leave_code": None,
        "clinic_code": member.clinic_code,
    }
    return plan


def plan_not_found(patient: Patient) -> PatientPlan:
    plan = PatientPlan(patient)
    plan.report(NO_ENCONTRADO, "No esta en la replica de SERMED. Su expediente se conserva.")
    plan.state = {"found": False}
    return plan


def apply_plan(plan: PatientPlan) -> dict[str, bool]:
    """Aplica un plan en una transaccion. Todo cambio queda en la bitacora."""
    patient = plan.patient
    applied = {"patient": False, "state": False, "identifier": False}
    with transaction.atomic():
        if plan.fields:
            previous = snapshot(patient, plan.fields)
            for attr, value in plan.fields.items():
                setattr(patient, attr, value)
            patient.save(update_fields=[*plan.fields, "updated_at"])
            record_change(
                table="cns_paciente", key=build_key("id_paciente", patient.pk),
                action=ChangeLog.Action.UPDATE, reason=ChangeLog.Reason.SERMED_SYNC,
                user=PROCESS_SERMED_SYNC, previous=previous, new=dict(plan.fields),
            )
            applied["patient"] = True

        state = PatientSermedState.objects.filter(patient=patient).first()
        if state is None:
            PatientSermedState.objects.create(patient=patient, **plan.state)
            applied["state"] = True
        else:
            previous = snapshot(state, plan.state)
            if previous != plan.state:
                for attr, value in plan.state.items():
                    setattr(state, attr, value)
                state.save()
                # Cambio de vigencia, baja, titular o parentesco (documento 5.1).
                record_change(
                    table="cns_paciente_sermed", key=build_key("id_paciente", patient.pk),
                    action=ChangeLog.Action.UPDATE, reason=ChangeLog.Reason.SERMED_SYNC,
                    user=PROCESS_SERMED_SYNC, previous=previous, new=dict(plan.state),
                )
                applied["state"] = True

        if plan.register_pk_num:
            try:
                _, created = register_identifier(
                    patient, PatientIdentifier.IdType.PK_NUM, patient.pk_num,
                    reason=ChangeLog.Reason.SERMED_SYNC, user=PROCESS_SERMED_SYNC,
                )
                applied["identifier"] = created
            except IdentifierConflict as exc:
                plan.report(IDENTIFICADOR_EN_CONFLICTO, str(exc))
    return applied


@dataclass
class SyncResult:
    counts: dict[str, int] = field(default_factory=dict)
    discrepancies: list[Discrepancy] = field(default_factory=list)

    def add(self, key: str, amount: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + amount


def sync_patients(patients: Iterable[Patient], *, source=None, dry_run: bool = False,
                  chunk_size: int = 500) -> SyncResult:
    """Sincroniza los pacientes dados contra la replica de SERMED."""
    source = source or ReplicaSermedSource()
    result = SyncResult()
    batch: list[Patient] = []

    def flush():
        titulares = [p for p in batch if p.pk_num == 0]
        familiares = [p for p in batch if p.pk_num]
        employees = source.employees({str(p.no_exp) for p in titulares}) if titulares else {}
        members = source.family_members({p.pk_num for p in familiares}) if familiares else {}
        for patient in batch:
            if patient.pk_num is None:
                result.add("familiares_solo_legado")  # sin PK_NUM: no estan en SERMED
                continue
            if patient.pk_num == 0:
                person = employees.get(str(patient.no_exp))
                plan = plan_employee(patient, person) if person else plan_not_found(patient)
            else:
                person = members.get(patient.pk_num)
                plan = plan_family_member(patient, person) if person else plan_not_found(patient)
            result.add("procesados")
            if plan.fields:
                result.add("pacientes_actualizados")
            if not dry_run:
                applied = apply_plan(plan)
                if applied["state"]:
                    result.add("estados_sermed_cambiados")
                if applied["identifier"]:
                    result.add("pk_num_registrados")
            result.discrepancies.extend(plan.discrepancies)
        batch.clear()

    for patient in patients:
        batch.append(patient)
        if len(batch) >= chunk_size:
            flush()
    if batch:
        flush()
    for discrepancy in result.discrepancies:
        result.add(f"discrepancia_{discrepancy.kind}")
    return result


def sync_no_exp(no_exp: str, *, source=None, dry_run: bool = False) -> SyncResult:
    """Sincroniza al titular y a los familiares de un expediente (tras actualizar_expediente)."""
    patients = Patient.objects.filter(no_exp=str(no_exp).strip()).order_by("id_patient")
    return sync_patients(patients, source=source, dry_run=dry_run)
