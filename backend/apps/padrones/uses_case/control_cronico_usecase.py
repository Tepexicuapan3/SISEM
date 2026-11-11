"""
Cronicos, entrega 2 (docs/plans/cronicos-control.md): control de un programa
en la consulta, con metas y semaforo.

Reglas:
- El panel lo ve quien ve el aviso (clinico:consultas:read o
  clinico:padrones:read). Registrar pide clinico:cronicos:control.
- Un programa entra al panel si el paciente tiene una inscripcion activa con
  un CIE de ese programa que el usuario puede ver.
- Los valores de somatometria los toma el backend por el contrato de
  somatometria; el cliente solo manda los de captura manual.
- Un control por programa y visita, solo con la visita en consulta. No se
  edita ni se borra; cada medicion guarda la meta vigente.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.authentication.services.permission_dependencies import evaluate_permission_requirement
from apps.padrones.domain import control_cronico as rules
from apps.padrones.models import (
    Adherence,
    ChronicControl,
    ChronicControlGoal,
    ChronicControlMeasurement,
    ChronicEnrollment,
    ChronicProgram,
    ControlParameter,
    MeasurementSource,
    RegistryStatus,
)
from apps.recepcion.services.errors import VisitDomainError
from apps.somatometria.contracts import vitals_for_visit

from . import padron_usecase as padron
from .aviso_consulta_usecase import CHRONIC, NOTICE_REQUIREMENT, _visit_or_404, program_for_cie

CONTROL_REQUIREMENT = {"allOf": ["clinico:cronicos:control"]}
MIN_MANUAL_VALUE = Decimal("0")
MAX_MANUAL_VALUE = Decimal("1000")


@dataclass(frozen=True)
class ParameterSpec:
    unit: str
    source: str
    vitals_key: str | None = None


P = ControlParameter
SOMA = MeasurementSource.SOMATOMETRIA
MANUAL = MeasurementSource.MANUAL
PARAMETERS = {
    P.TA_SISTOLICA: ParameterSpec("mmHg", SOMA, "blood_pressure_systolic"),
    P.TA_DIASTOLICA: ParameterSpec("mmHg", SOMA, "blood_pressure_diastolic"),
    P.GLUCOSA_CAPILAR: ParameterSpec("mg/dL", SOMA, "glucosa_capilar_mgdl"),
    P.IMC: ParameterSpec("kg/m²", SOMA, "bmi"),
    P.PESO: ParameterSpec("kg", SOMA, "weight_kg"),
    P.CINTURA: ParameterSpec("cm", SOMA, "waist_circumference_cm"),
    P.HBA1C: ParameterSpec("%", MANUAL),
    P.COLESTEROL_TOTAL: ParameterSpec("mg/dL", MANUAL),
    P.LDL: ParameterSpec("mg/dL", MANUAL),
    P.TRIGLICERIDOS: ParameterSpec("mg/dL", MANUAL),
}
# Se muestran siempre, sin semaforo si el programa no les pone meta.
INFORMATIVE = (P.PESO, P.CINTURA)


def _number(value):
    return float(value) if value is not None else None


def _visible_programs(patient_id, permissions, roles):
    """Programas activos de las inscripciones activas que el usuario puede ver."""
    programs = {}
    enrollments = ChronicEnrollment.objects.select_related("cie").filter(
        patient_id=patient_id, status=RegistryStatus.ACTIVO,
    ).order_by("enrolled_on", "id")
    for enrollment in enrollments:
        if padron._item_payload(CHRONIC, enrollment, permissions, roles)["restricted"]:
            continue
        program = program_for_cie(enrollment.cie_id)
        if program is not None:
            programs.setdefault(program.pk, program)
    return list(programs.values())


def _rows(program, vitals, manual_values):
    """Una fila por parametro del programa (metas + informativos), con su valor."""
    goals = {g.parameter: g for g in ChronicControlGoal.objects.filter(program=program)}
    order = [p for p in ControlParameter if p in goals or p in INFORMATIVE]
    rows = []
    for parameter in order:
        spec = PARAMETERS[parameter]
        goal = goals.get(parameter)
        if spec.source == SOMA:
            raw = (vitals or {}).get(spec.vitals_key)
            value = Decimal(str(raw)) if raw is not None else None
        else:
            value = manual_values.get(parameter)
        goal_min = goal.min_value if goal else None
        goal_max = goal.max_value if goal else None
        rows.append({
            "parameter": parameter, "spec": spec, "has_goal": goal is not None,
            "value": value, "goal_min": goal_min, "goal_max": goal_max,
            "in_goal": rules.in_goal(value, goal_min, goal_max),
        })
    return rows


def _status(rows):
    return rules.control_status([r["in_goal"] for r in rows if r["has_goal"]])


def _row_contract(row):
    return {
        "parameter": row["parameter"],
        "label": ControlParameter(row["parameter"]).label,
        "unit": row["spec"].unit,
        "source": row["spec"].source,
        "value": _number(row["value"]),
        "goalMin": _number(row["goal_min"]),
        "goalMax": _number(row["goal_max"]),
        "inGoal": row["in_goal"],
    }


def _registered_by(user):
    return padron._user_name(user)


def control_contract(control):
    return {
        "id": control.id,
        "program": {"code": control.program.code, "name": control.program.name},
        "controlOn": control.control_on,
        "status": control.status,
        "nextControlOn": control.next_control_on,
        "adherence": control.adherence,
        "notes": control.notes,
        "registeredBy": _registered_by(control.registered_by),
        "measurements": [
            {
                "parameter": m.parameter,
                "label": ControlParameter(m.parameter).label,
                "unit": m.unit,
                "source": m.source,
                "value": _number(m.value),
                "goalMin": _number(m.goal_min),
                "goalMax": _number(m.goal_max),
                "inGoal": m.in_goal,
            }
            for m in control.measurements.order_by("id")
        ],
    }


def _controls():
    return ChronicControl.objects.select_related("program", "registered_by__detalle").prefetch_related("measurements")


def get_control_panel(visit_id, *, permissions, roles=None):
    padron._ensure(NOTICE_REQUIREMENT, permissions)
    roles = roles or []
    visit = _visit_or_404(visit_id)
    vitals = vitals_for_visit(visit.id_visit)
    today = timezone.localdate()
    entries = []
    for program in _visible_programs(visit.patient_id, permissions, roles):
        rows = _rows(program, vitals, {})
        registered = _controls().filter(program=program, visit_id=visit.id_visit).first()
        last = (
            ChronicControl.objects.filter(patient_id=visit.patient_id, program=program)
            .exclude(visit_id=visit.id_visit).order_by("-control_on", "-id").first()
        )
        entries.append({
            "program": {"code": program.code, "name": program.name},
            "everyDays": program.control_every_days,
            "parameters": [_row_contract(r) for r in rows],
            "status": _status(rows),
            "suggestedNextControlOn": today + timedelta(days=program.control_every_days),
            "registered": control_contract(registered) if registered else None,
            "last": None if last is None else {
                "controlOn": last.control_on,
                "status": last.status,
                "nextControlOn": last.next_control_on,
                "overdue": last.next_control_on < today,
            },
        })
    return {
        "programs": entries,
        "vitalsCapturedAt": vitals["captured_at"] if vitals else None,
        "canRegister": evaluate_permission_requirement(CONTROL_REQUIREMENT, permissions or [])["granted"],
    }


def _parse_manual_values(values, program):
    manual_with_goal = set(
        ChronicControlGoal.objects.filter(program=program).values_list("parameter", flat=True)
    ) & {p for p, spec in PARAMETERS.items() if spec.source == MANUAL}
    parsed = {}
    for parameter, raw in (values or {}).items():
        if parameter not in manual_with_goal:
            raise padron._validation_error(
                "values", f"'{parameter}' no se captura a mano en el programa {program.name}.",
            )
        if raw in (None, ""):
            continue
        try:
            value = Decimal(str(raw)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise padron._validation_error("values", f"El valor de '{parameter}' no es un número.") from None
        if not (MIN_MANUAL_VALUE < value < MAX_MANUAL_VALUE):
            raise padron._validation_error("values", f"El valor de '{parameter}' está fuera de rango.")
        parsed[parameter] = value
    return parsed


def register_control(visit_id, *, program_code, values=None, adherence=None, notes=None, actor, permissions):
    padron._ensure(CONTROL_REQUIREMENT, permissions)
    visit = _visit_or_404(visit_id)
    program = ChronicProgram.objects.filter(code=(program_code or "").strip().upper(), is_active=True).first()
    if program is None:
        raise padron._validation_error("programCode", "El programa no existe o no está activo.")
    enrolled = any(
        program_for_cie(cie) == program
        for cie in ChronicEnrollment.objects.filter(
            patient_id=visit.patient_id, status=RegistryStatus.ACTIVO,
        ).values_list("cie_id", flat=True)
    )
    if not enrolled:
        raise padron._validation_error("programCode", "El paciente no está inscrito en ese programa.")
    if adherence not in (None, "", *Adherence.values):
        raise padron._validation_error("adherence", "Debe ser buena, regular o mala.")
    manual_values = _parse_manual_values(values, program)
    if visit.status != "en_consulta":
        raise VisitDomainError(
            "VISIT_NOT_IN_CONSULTATION", "El control se registra con la consulta en curso.", 409,
        )
    center = padron._resolve_center(visit.centro_id, actor)
    rows = _rows(program, vitals_for_visit(visit.id_visit), manual_values)
    today = timezone.localdate()

    try:
        with transaction.atomic():
            if ChronicControl.objects.filter(program=program, visit_id=visit.id_visit).exists():
                raise VisitDomainError(
                    "CONTROL_ALREADY_REGISTERED", "Ya se registró el control de este programa en la consulta.", 409,
                )
            control = ChronicControl.objects.create(
                patient_id=visit.patient_id, program=program, visit_id=visit.id_visit, center=center,
                control_on=today, status=_status(rows),
                next_control_on=today + timedelta(days=program.control_every_days),
                adherence=adherence or None, notes=(notes or "").strip() or None, registered_by=actor,
            )
            ChronicControlMeasurement.objects.bulk_create([
                ChronicControlMeasurement(
                    control=control, parameter=r["parameter"], value=r["value"], unit=r["spec"].unit,
                    source=r["spec"].source, goal_min=r["goal_min"], goal_max=r["goal_max"], in_goal=r["in_goal"],
                )
                for r in rows if r["value"] is not None
            ])
    except IntegrityError as exc:  # carrera contra el unique programa + visita
        raise VisitDomainError(
            "CONTROL_ALREADY_REGISTERED", "Ya se registró el control de este programa en la consulta.", 409,
        ) from exc
    return _controls().get(pk=control.pk)
