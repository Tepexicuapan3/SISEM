"""
GRUPO_SANGUINEO (documento "Historia Clinica Unificada", 5.2): tipo de sangre
del paciente con su fuente (L laboratorio, D declarado) y su historial.

- Primera captura: alta de la fila vigente. No va a la bitacora de cambios
  (el alta ya queda en usr_alta/fch_alta, regla 3 del documento).
- Cambio: la vigente pasa a B (no se borra), se crea la nueva y el porque va
  a cns_bitacora_cambios con el motivo CORRECCION. El motivo escrito por el
  medico es obligatorio y viaja en valor_nuevo.
- Mismo tipo, fuente y resultado que el vigente: no hace nada.
"""
from django.db import transaction
from django.db.models import Q

from apps.catalogos.models import TiposSanguineo
from apps.consulta_medica.models import BloodType, ChangeLog, StudyResult
from apps.consulta_medica.repositories.clinical_history_repository import ClinicalHistoryRepository
from apps.consulta_medica.services.change_log_service import build_key, record_change
from apps.recepcion.services.errors import VisitDomainError

from .consultation_usecase import ensure_doctor_role

_LOGGED_FIELDS = ("blood_type_id", "source", "lab_result_id")


def _validation_error(details):
    return VisitDomainError("VALIDATION_ERROR", "Hay errores en el formulario", 422, details=details)


def _to_contract(record):
    return {
        "id": record.id_blood_type,
        "bloodTypeId": record.blood_type_id,
        "bloodTypeName": record.blood_type.name,
        "source": record.source,
        "labResultId": record.lab_result_id,
        "status": record.status,
        "createdAt": record.created_at,
        "createdById": record.created_by_id,
        "updatedAt": record.updated_at,
    }


def _payload(patient):
    # Plan identidad, Fase 4: el grupo sanguineo es de la PERSONA (todas sus
    # afiliaciones). Una contradiccion entre registros vinculados se alerta en
    # la Fase 7; hoy cada persona tiene un solo registro.
    records = list(
        BloodType.objects.filter(patient__person_id=patient.person_id)
        .select_related("blood_type")
        .order_by("-created_at", "-id_blood_type")
    )
    current = next((record for record in records if record.status == BloodType.Status.ACTIVE), None)
    activos = {record.blood_type_id for record in records if record.status == BloodType.Status.ACTIVE}
    return {
        "current": _to_contract(current) if current else None,
        "history": [_to_contract(record) for record in records if record is not current],
        # Plan identidad, Fase 7: dos registros vinculados de la misma persona
        # con grupos distintos. Nunca se elige uno en silencio: se alerta.
        "conflict": len(activos) > 1,
    }


def _patient_for(no_exp, pk_num):
    history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
    return history.patient


def get_blood_type(no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    return _payload(_patient_for(no_exp, pk_num))


def _validate(patient, validated_data):
    blood_type_id = validated_data["bloodTypeId"]
    if not TiposSanguineo.objects.filter(pk=blood_type_id, is_active=True).exists():
        raise _validation_error({"bloodTypeId": ["Tipo de sangre invalido."]})

    source = validated_data["source"]
    lab_result_id = validated_data.get("labResultId")
    if lab_result_id is not None:
        if source != BloodType.Source.LAB:
            raise _validation_error({"labResultId": ["Solo un tipo de sangre de laboratorio lleva resultado."]})
        # El resultado tiene que ser de ESTE paciente: si no, el respaldo es de
        # otra persona. Mientras id_paciente siga nullable (etapa 7e), tambien
        # vale el resultado aun no vinculado con la misma llave no_exp/pk_num.
        same_patient = Q(patient=patient) | Q(
            patient__isnull=True, no_exp=patient.no_exp, pk_num=patient.pk_num,
        )
        if not StudyResult.objects.filter(same_patient, pk=lab_result_id, is_active=True).exists():
            raise _validation_error({"labResultId": ["El resultado no existe o no es de este paciente."]})
    return blood_type_id, source, lab_result_id


def set_blood_type(no_exp, pk_num, roles, validated_data, actor_id, permissions=None, *, audit_hook):
    ensure_doctor_role(roles, permissions)
    patient = _patient_for(no_exp, pk_num)
    blood_type_id, source, lab_result_id = _validate(patient, validated_data)
    reason = (validated_data.get("reason") or "").strip()

    with transaction.atomic():
        current = (
            BloodType.objects.select_for_update()
            .filter(patient=patient, status=BloodType.Status.ACTIVE)
            .first()
        )
        new_values = {"blood_type_id": blood_type_id, "source": source, "lab_result_id": lab_result_id}

        if current is not None:
            previous_values = {field: getattr(current, field) for field in _LOGGED_FIELDS}
            if previous_values == new_values:
                return _payload(patient)
            if not reason:
                raise _validation_error(
                    {"reason": ["Escribe por que cambia el tipo de sangre: queda en la bitacora."]}
                )
            current.status = BloodType.Status.CORRECTED
            current.updated_by_id = actor_id
            current.save(update_fields=["status", "updated_by_id", "updated_at"])

        record = BloodType.objects.create(
            patient=patient, created_by_id=actor_id, updated_by_id=actor_id, **new_values,
        )

        if current is not None:
            record_change(
                table="cns_grupo_sanguineo",
                key=build_key("id_paciente", patient.id_patient),
                action=ChangeLog.Action.UPDATE,
                reason=ChangeLog.Reason.CORRECTION,
                user=actor_id,
                previous=previous_values,
                new={**new_values, "motivo": reason[:500]},
            )

        audit_hook(
            resource_id=record.id_blood_type,
            datos_antes=(
                {"bloodTypeId": previous_values["blood_type_id"], "source": previous_values["source"]}
                if current is not None else None
            ),
            datos_despues={"bloodTypeId": blood_type_id, "source": source, "labResultId": lab_result_id},
        )

    return _payload(patient)
