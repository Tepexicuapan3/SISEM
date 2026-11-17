"""
Inscripcion y baja en los padrones clinicos (P-04).

Reglas:
- Permisos propios: clinico:padrones:read (consulta) y clinico:padrones:write
  (inscribir / dar de baja).
- El paciente se resuelve con PatientRepository.get_or_create, el mismo
  contrato que usa la historia clinica.
- Centro: el indicado o, si no se indica, el de adscripcion del usuario.
- Una sola inscripcion activa por paciente y padecimiento; la baja es logica,
  por inscripcion, con motivo de catalogo y fecha no futura.
- Los diagnosticos CIE-10 sensibles se redactan segun quien consulta, igual
  que en el resto del expediente.
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Case, F, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.lookups import StartsWith
from django.utils import timezone

from apps.authentication.services.permission_dependencies import evaluate_permission_requirement
from apps.catalogos.models import CatCentroAtencion, CatCies, Discapacidades, MotivoBajaPadron
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
from apps.consulta_medica.services.diagnosis_redaction_service import redact_cie_if_restricted
from apps.padrones.models import (
    ChronicControl,
    ChronicEnrollment,
    ChronicProgram,
    ChronicProgramCie,
    DisabilityEnrollment,
    EnrollmentSource,
    RegistryStatus,
)
from apps.recepcion.contracts.patient_lookup_contract import family_members
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import q_pk_registro
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp
from apps.consulta_medica.services.paciente_entrada import llave_publica

READ_REQUIREMENT = {"allOf": ["clinico:padrones:read"]}
WRITE_REQUIREMENT = {"allOf": ["clinico:padrones:write"]}
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class RegistryKind:
    key: str
    model: type
    item_field: str  # FK del padecimiento en el modelo
    item_model: type
    item_label: str


KINDS = {
    "cronicos": RegistryKind("cronicos", ChronicEnrollment, "cie", CatCies, "El diagnóstico CIE-10"),
    "discapacidad": RegistryKind(
        "discapacidad", DisabilityEnrollment, "disability", Discapacidades, "La discapacidad",
    ),
}


def _validation_error(field, message):
    return VisitDomainError("VALIDATION_ERROR", "Hay errores en el formulario", 422, details={field: [message]})


def _ensure(requirement, permissions):
    if not evaluate_permission_requirement(requirement, permissions or [])["granted"]:
        raise VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso para ejecutar esta accion.", 403)


def get_kind(kind):
    spec = KINDS.get(kind)
    if spec is None:
        raise VisitDomainError("REGISTRY_NOT_FOUND", "Padrón no encontrado.", 404)
    return spec


def _user_name(user):
    if user is None:
        return None
    profile = getattr(user, "detalle", None)
    return getattr(profile, "nombre_completo", None) or user.usuario


def _patient_name(patient):
    parts = (patient.first_name, patient.paternal_surname, patient.maternal_surname)
    return " ".join(p.strip() for p in parts if p and p.strip()) or None


def _item_payload(spec, enrollment, permissions, roles):
    item = getattr(enrollment, spec.item_field)
    if spec.key == "cronicos":
        code, description, _, restricted = redact_cie_if_restricted(
            code=item.code, description=item.description, permissions=permissions, roles=roles,
        )
        return {"id": code, "code": code, "description": description, "restricted": restricted}
    return {"id": item.pk, "code": item.code, "description": item.name, "restricted": False}


def _chronic_contract(enrollment, item):
    """Programa y ultimo control (anotados por _with_program_and_last_control).
    Un CIE redactado no muestra programa: lo delataria."""
    code = getattr(enrollment, "program_code", None)
    last_on = getattr(enrollment, "last_control_on", None)
    next_on = getattr(enrollment, "last_next_control_on", None)
    return {
        "program": None if item["restricted"] or not code else {"code": code, "name": enrollment.program_name},
        "lastControl": None if last_on is None else {
            "controlOn": last_on,
            "status": enrollment.last_control_status,
            "nextControlOn": next_on,
            "overdue": next_on < timezone.localdate(),
        },
    }


def to_contract(spec, enrollment, *, permissions, roles):
    item = _item_payload(spec, enrollment, permissions, roles)
    return {
        "id": enrollment.id,
        "registry": spec.key,
        "noExp": llave_publica(enrollment)[0],
        "pkNum": llave_publica(enrollment)[1],
        "patientName": _patient_name(enrollment.patient),
        "item": item,
        "center": {"id": enrollment.center_id, "name": enrollment.center.name},
        "enrolledOn": enrollment.enrolled_on,
        "enrolledBy": _user_name(enrollment.enrolled_by),
        "notes": enrollment.notes,
        # Origen del diagnostico (solo cronicos; null en inscripciones anteriores).
        "source": getattr(enrollment, "source", None),
        "status": enrollment.status,
        **(_chronic_contract(enrollment, item) if spec.key == "cronicos" else {}),
        "discharge": None if enrollment.status == RegistryStatus.ACTIVO else {
            "reasonId": enrollment.discharge_reason_id,
            "reason": getattr(enrollment.discharge_reason, "name", None),
            "detail": enrollment.discharge_detail,
            "on": enrollment.discharged_on,
            "by": _user_name(enrollment.discharged_by),
        },
    }


def _base_queryset(spec):
    qs = spec.model.objects.select_related(
        "patient", "center", spec.item_field, "enrolled_by__detalle",
        "discharge_reason", "discharged_by__detalle",
    )
    return _with_program_and_last_control(qs) if spec.key == "cronicos" else qs


CONTROL_FILTERS = ("vencido", "al_dia", "sin_control")


def _with_program_and_last_control(qs):
    """Programa del CIE (prefijo mas largo, como program_for_cie) y ultimo
    control del paciente en ese programa (docs/plans/cronicos-gestion-padron.md)."""
    program = (
        ChronicProgramCie.objects.filter(StartsWith(OuterRef("cie_id"), F("cie_prefix")), program__is_active=True)
        .order_by("-cie_prefix")[:1]
    )
    last = ChronicControl.objects.filter(
        patient_id=OuterRef("patient_id"), program_id=OuterRef("program_id"),
    ).order_by("-control_on", "-id")
    return qs.annotate(
        program_id=Subquery(program.values("program_id")),
        program_code=Subquery(program.values("program__code")),
        program_name=Subquery(program.values("program__name")),
    ).annotate(
        last_control_on=Subquery(last.values("control_on")[:1]),
        last_control_status=Subquery(last.values("status")[:1]),
        last_next_control_on=Subquery(last.values("next_control_on")[:1]),
    )


def _chronic_filters(qs, *, program, control):
    if program:
        program_id = ChronicProgram.objects.filter(code=program.strip().upper(), is_active=True).values_list(
            "pk", flat=True,
        ).first()
        if program_id is None:
            raise _validation_error("program", "El programa no existe o no está activo.")
        qs = qs.filter(program_id=program_id)
    if control:
        if control not in CONTROL_FILTERS:
            raise _validation_error("control", "Debe ser 'vencido', 'al_dia' o 'sin_control'.")
        today = timezone.localdate()
        qs = {
            "vencido": lambda: qs.filter(last_next_control_on__lt=today),
            "al_dia": lambda: qs.filter(last_next_control_on__gte=today),
            "sin_control": lambda: qs.filter(program_id__isnull=False, last_control_on__isnull=True),
        }[control]()
    return qs


PRIORITY_ORDER = "prioridad"


def _priority_order(qs):
    """Lista de trabajo (docs/plans/padrones-correccion-y-prioridad.md): vencido,
    sin control, al dia, sin programa y al final las bajas; dentro de cada grupo
    el proximo control mas antiguo primero."""
    today = timezone.localdate()
    rank = Case(
        When(status=RegistryStatus.BAJA, then=Value(4)),
        When(last_next_control_on__lt=today, then=Value(0)),
        When(program_id__isnull=False, last_control_on__isnull=True, then=Value(1)),
        When(program_id__isnull=False, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )
    return qs.annotate(priority=rank).order_by(
        "priority", F("last_next_control_on").asc(nulls_last=True), "-enrolled_on", "-id",
    )


def _name_filter(qs, search):
    for word in (search or "").split():
        qs = qs.filter(
            Q(patient__first_name__icontains=word) | Q(patient__paternal_surname__icontains=word)
            | Q(patient__maternal_surname__icontains=word)
        )
    return qs


def list_programs(*, permissions):
    _ensure(READ_REQUIREMENT, permissions)
    programs = ChronicProgram.objects.filter(is_active=True).order_by("name")
    return {"items": [{"code": p.code, "name": p.name} for p in programs]}


def list_enrollments(kind, *, permissions, roles=None, no_exp=None, pk_num=None, center_id=None,
                     status=None, page=1, page_size=20, program=None, control=None, search=None, order=None):
    _ensure(READ_REQUIREMENT, permissions)
    spec = get_kind(kind)
    qs = _base_queryset(spec)
    if spec.key == "cronicos":
        qs = _chronic_filters(qs, program=program, control=control)
    elif program or control or order:
        field = "program" if program else "control" if control else "order"
        raise _validation_error(field, "Solo aplica al padrón de crónicos.")
    if order and order != PRIORITY_ORDER:
        raise _validation_error("order", "Debe ser 'prioridad'.")
    qs = _name_filter(qs, search)
    if no_exp:
        # Plan contraer la llave vieja: el expediente se busca en cns_paciente.
        qs = qs.filter(patient__no_exp=normalizar_no_exp(no_exp))
        if pk_num is not None:
            qs = qs.filter(q_pk_registro(pk_num))
    if center_id:
        qs = qs.filter(center_id=center_id)
    if status:
        if status not in RegistryStatus.values:
            raise _validation_error("status", "Debe ser 'activo' o 'baja'.")
        qs = qs.filter(status=status)

    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), MAX_PAGE_SIZE)
    total = qs.count()
    qs = _priority_order(qs) if order else qs.order_by("-enrolled_on", "-id")
    rows = qs[(page - 1) * page_size: page * page_size]
    return {
        "items": [to_contract(spec, e, permissions=permissions, roles=roles or []) for e in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": max((total + page_size - 1) // page_size, 1),
    }


PATIENT_REGISTRIES_REQUIREMENT = {
    "anyOf": ["clinico:expedientes:read", "clinico:consultas:read", "clinico:padrones:read"],
}


def patient_registries(patient_id, *, permissions, roles=None):
    """Inscripciones activas del paciente en ambos padrones, para la alerta del
    expediente (docs/plans/padrones-alerta-expediente.md). Un id desconocido da
    listas vacias: no confirma si el paciente existe."""
    _ensure(PATIENT_REGISTRIES_REQUIREMENT, permissions)
    return {
        key: [
            to_contract(spec, e, permissions=permissions, roles=roles or [])
            for e in _base_queryset(spec).filter(patient_id=patient_id, status=RegistryStatus.ACTIVO)
            .order_by("enrolled_on", "id")
        ]
        for key, spec in KINDS.items()
    }


def search_options(kind, *, search, permissions, roles=None, limit=20):
    """Opciones para inscribir, con el permiso del padron (no el de consulta
    ni el de admin de catalogos). Los CIE-10 sensibles que el usuario no puede
    ver se omiten: una opcion redactada no sirve para elegir."""
    _ensure(WRITE_REQUIREMENT, permissions)
    spec = get_kind(kind)
    term = (search or "").strip()
    if len(term) < 2:
        return {"items": []}
    if spec.key == "cronicos":
        # Import tardio: aviso_consulta_usecase importa este modulo.
        from apps.padrones.uses_case.aviso_consulta_usecase import program_for_cie

        qs = CatCies.objects.filter(is_active=True).filter(
            Q(code__istartswith=term) | Q(description__icontains=term)
        ).order_by("code")
        items = []
        for cie in qs[: limit * 3]:
            _, _, _, restricted = redact_cie_if_restricted(
                code=cie.code, description=cie.description, permissions=permissions, roles=roles or [],
            )
            if not restricted:
                # El programa orienta: un CIE sin programa se puede inscribir igual
                # (hay cronicos fuera de los programas), la pantalla lo avisa.
                program = program_for_cie(cie.code)
                items.append({
                    "id": cie.code, "code": cie.code, "description": cie.description,
                    "program": {"code": program.code, "name": program.name} if program else None,
                })
            if len(items) >= limit:
                break
        return {"items": items}
    qs = Discapacidades.objects.filter(is_active=True).filter(
        Q(code__istartswith=term) | Q(name__icontains=term)
    ).order_by("code")[:limit]
    return {"items": [{"id": d.pk, "code": d.code, "description": d.name} for d in qs]}


def family_for_enrollment(no_exp, *, permissions):
    """Titular y derechohabientes vigentes del expediente, para elegir a la
    persona en el alta (el pkNum no se escribe a mano)."""
    _ensure(WRITE_REQUIREMENT, permissions)
    no_exp = (no_exp or "").strip()
    if not no_exp:
        raise _validation_error("noExp", "El expediente es obligatorio.")
    return {"members": family_members(no_exp)}


def _assignment_center_id(user):
    try:
        return user.detalle.id_centro_atencion_id
    except Exception:
        return None


def _resolve_center(center_id, actor):
    center_id = center_id or _assignment_center_id(actor)
    if not center_id:
        raise _validation_error("centerId", "Indica el centro: el usuario no tiene centro de adscripción.")
    center = CatCentroAtencion.objects.filter(pk=center_id, is_active=True).first()
    if center is None:
        raise _validation_error("centerId", "El centro no existe o no está activo.")
    return center


def _ensure_not_future(field, value):
    if value > timezone.localdate():
        raise _validation_error(field, "La fecha no puede ser futura.")


def enroll(kind, *, no_exp, pk_num, item_id, center_id=None, enrolled_on=None, notes=None,
           actor, permissions):
    _ensure(WRITE_REQUIREMENT, permissions)
    spec = get_kind(kind)
    no_exp = (no_exp or "").strip()
    if not no_exp:
        raise _validation_error("noExp", "El expediente es obligatorio.")
    item = spec.item_model.objects.filter(pk=item_id, is_active=True).first()
    if item is None:
        raise _validation_error("itemId", f"{spec.item_label} no existe o no está activo.")
    center = _resolve_center(center_id, actor)
    enrolled_on = enrolled_on or timezone.localdate()
    _ensure_not_future("enrolledOn", enrolled_on)
    return create_enrollment(
        spec, get_patient=lambda: PatientRepository.get_or_create(no_exp, pk_num or 0, created_by_id=actor.pk)[0],
        item=item, center=center, enrolled_on=enrolled_on, notes=notes, actor=actor,
        extra={"source": EnrollmentSource.MANUAL} if spec.key == "cronicos" else None,
    )


def create_enrollment(spec, *, get_patient, item, center, enrolled_on, notes, actor, extra=None):
    """Crea la inscripcion activa (ya validados item, centro y fecha). Lo usan
    el alta del padron y la inscripcion desde la consulta. `extra`: campos
    propios del padron (origen y visita en cronicos)."""
    try:
        with transaction.atomic():
            patient = get_patient()
            if patient.birth_date and enrolled_on < patient.birth_date:
                raise _validation_error("enrolledOn", "La inscripción no puede ser anterior al nacimiento.")
            already = spec.model.objects.filter(
                patient=patient, status=RegistryStatus.ACTIVO, **{spec.item_field: item},
            ).exists()
            if already:
                raise VisitDomainError(
                    "ALREADY_ENROLLED", "El paciente ya está inscrito en el padrón por ese padecimiento.", 409,
                )
            enrollment = spec.model.objects.create(
                patient=patient, center=center,
                enrolled_on=enrolled_on, enrolled_by=actor, notes=(notes or "").strip() or None,
                **{spec.item_field: item}, **(extra or {}),
            )
    except IntegrityError as exc:  # carrera contra el unique de inscripcion activa
        raise VisitDomainError(
            "ALREADY_ENROLLED", "El paciente ya está inscrito en el padrón por ese padecimiento.", 409,
        ) from exc
    return _base_queryset(spec).get(pk=enrollment.pk)


def discharge(kind, enrollment_id, *, reason_id, detail=None, discharged_on=None, actor, permissions):
    _ensure(WRITE_REQUIREMENT, permissions)
    spec = get_kind(kind)
    reason = MotivoBajaPadron.objects.filter(pk=reason_id, is_active=True).first()
    if reason is None:
        raise _validation_error("reasonId", "El motivo de baja no existe o no está activo.")
    discharged_on = discharged_on or timezone.localdate()
    _ensure_not_future("dischargedOn", discharged_on)

    with transaction.atomic():
        enrollment = spec.model.objects.select_for_update().filter(pk=enrollment_id).first()
        if enrollment is None:
            raise VisitDomainError("ENROLLMENT_NOT_FOUND", "Inscripción no encontrada.", 404)
        if enrollment.status != RegistryStatus.ACTIVO:
            raise VisitDomainError("ENROLLMENT_ALREADY_DISCHARGED", "La inscripción ya está dada de baja.", 409)
        if discharged_on < enrollment.enrolled_on:
            raise _validation_error("dischargedOn", "La baja no puede ser anterior a la inscripción.")
        enrollment.status = RegistryStatus.BAJA
        enrollment.discharge_reason = reason
        enrollment.discharge_detail = (detail or "").strip() or None
        enrollment.discharged_on = discharged_on
        enrollment.discharged_by = actor
        enrollment.save(update_fields=[
            "status", "discharge_reason", "discharge_detail", "discharged_on", "discharged_by", "updated_at",
        ])
    return _base_queryset(spec).get(pk=enrollment.pk)


CORRECTION_REASON = "Registro erróneo"
KEEP = object()  # "no se manda": la correccion conserva el valor


def _ensure_visible_item(spec, item, permissions, roles):
    if spec.key != "cronicos":
        return
    _, _, _, restricted = redact_cie_if_restricted(
        code=item.code, description=item.description, permissions=permissions, roles=roles,
    )
    if restricted:
        raise VisitDomainError("ROLE_NOT_ALLOWED", "No tienes permiso para corregir este diagnóstico.", 403)


def correct(kind, enrollment_id, *, item_id=None, enrolled_on=None, notes=KEEP, detail,
            actor, permissions, roles=None):
    """Corrige una inscripcion mal capturada (docs/plans/padrones-correccion-y-prioridad.md):
    baja con motivo "Registro erroneo" y alta con los datos corregidos, en una
    transaccion. La inscripcion no se edita: el historial guarda ambas.
    Devuelve (original dada de baja, nueva)."""
    _ensure(WRITE_REQUIREMENT, permissions)
    spec = get_kind(kind)
    detail = (detail or "").strip()
    if not detail:
        raise _validation_error("detail", "Indica qué se corrigió.")
    reason = MotivoBajaPadron.objects.filter(name=CORRECTION_REASON, is_active=True).order_by("pk").first()
    if reason is None:
        raise VisitDomainError(
            "CORRECTION_REASON_MISSING",
            f"Falta el motivo de baja '{CORRECTION_REASON}' en el catálogo; pide al administrador que lo active.",
            409,
        )
    if enrolled_on is not None:
        _ensure_not_future("enrolledOn", enrolled_on)
    today = timezone.localdate()

    with transaction.atomic():
        original = spec.model.objects.select_for_update().filter(pk=enrollment_id).first()
        if original is None:
            raise VisitDomainError("ENROLLMENT_NOT_FOUND", "Inscripción no encontrada.", 404)
        if original.status != RegistryStatus.ACTIVO:
            raise VisitDomainError("ENROLLMENT_ALREADY_DISCHARGED", "La inscripción ya está dada de baja.", 409)
        current_item = getattr(original, spec.item_field)
        _ensure_visible_item(spec, current_item, permissions, roles or [])

        item = current_item
        if item_id not in (None, "") and str(item_id) != str(current_item.pk):
            item = spec.item_model.objects.filter(pk=item_id, is_active=True).first()
            if item is None:
                raise _validation_error("itemId", f"{spec.item_label} no existe o no está activo.")
            _ensure_visible_item(spec, item, permissions, roles or [])
        new_enrolled_on = enrolled_on or original.enrolled_on
        new_notes = original.notes if notes is KEEP else ((notes or "").strip() or None)
        if (item.pk, new_enrolled_on, new_notes) == (current_item.pk, original.enrolled_on, original.notes):
            raise _validation_error("itemId", "No hay cambios que corregir.")

        original.status = RegistryStatus.BAJA
        original.discharge_reason = reason
        original.discharged_on = today
        original.discharged_by = actor
        original.save(update_fields=["status", "discharge_reason", "discharged_on", "discharged_by", "updated_at"])

        extra = {"source": original.source, "visit_id": original.visit_id} if spec.key == "cronicos" else None
        created = create_enrollment(
            spec, get_patient=lambda: original.patient, item=item, center=original.center,
            enrolled_on=new_enrolled_on, notes=new_notes, actor=actor, extra=extra,
        )
        original.discharge_detail = f"Corregida por la inscripción #{created.pk}: {detail}"[:500]
        original.save(update_fields=["discharge_detail", "updated_at"])
    return _base_queryset(spec).get(pk=original.pk), created
