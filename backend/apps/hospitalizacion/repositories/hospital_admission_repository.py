from apps.hospitalizacion.models import HospitalAdmission, HospitalAdmissionRevision

# Campos editables via HospitalAdmissionUseCase.update -- mismo set que el
# field-map escribible del use-case. Se usa para saber que "previous_<campo>"
# snapshotear en HospitalAdmissionRevision. Calca
# ClinicalHistoryRepository._VERSIONED_FIELDS
# (apps/consulta_medica/repositories/clinical_history_repository.py:6-25).
#
# Campos NO versionados (identidad/evidencia de procedencia inmutable/
# auditoria de creacion) y por que -- ver Engram, topic_key
# sdd/his-hospital-modelo-nom024/design, Decision 1:
#   legacy_folio, no_exp, pk_num, admitting_doctor_code_legacy,
#   discharge_doctor_code_legacy, origin_center_code_legacy,
#   hospital_service_folio, clinical_note_code_legacy, registered_at,
#   registered_by_code_legacy, created_at/created_by_id, updated_at/
#   updated_by_id, deleted_at/deleted_by_id (viajan con is_active).
_VERSIONED_FIELDS = (
    "reason",
    "admission_type_id",
    "admission_date",
    "admission_time",
    "admitting_doctor_id",
    "discharge_date",
    "discharge_time",
    "discharge_doctor_id",
    "discharge_type_id",
    "is_scheduled",
    "origin_center_id",
    "external_folio",
    "is_active",
)


class HospitalAdmissionRepository:
    @staticmethod
    def update(admission, *, fields, updated_by_id=None, change_reason=None):
        # HospitalAdmission se captura de forma incremental (ver docstring
        # del modelo): rellenar un campo vacio por primera vez (p.ej. el
        # ALTA, que puede no existir todavia al ingreso) no es una
        # alteracion de un dato clinico/administrativo, es captura normal --
        # solo versiona cuando YA habia un valor concreto y se sobreescribe
        # con otro. Mismo criterio que ClinicalHistoryRepository.update.
        changed = any(
            field_name in fields
            and getattr(admission, field_name) not in (None, "")
            and getattr(admission, field_name) != value
            for field_name, value in fields.items()
        )
        if changed:
            # Versionado real (NOM-024): se guarda un snapshot del valor
            # anterior ANTES de pisarlo -- nunca se sobrescribe sin dejar
            # rastro. Snapshot de fila COMPLETA: todos los campos
            # versionados, no solo los que cambiaron (se reconstruye el
            # estado del ingreso en cualquier punto del tiempo).
            HospitalAdmissionRevision.objects.create(
                admission=admission,
                changed_by_id=updated_by_id,
                change_reason=change_reason,
                **{
                    f"previous_{field_name}": getattr(admission, field_name)
                    for field_name in _VERSIONED_FIELDS
                },
            )

        for field_name, value in fields.items():
            setattr(admission, field_name, value)
        admission.updated_by_id = updated_by_id
        admission.save()
        return admission
