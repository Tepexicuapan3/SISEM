import uuid

from django.db import transaction

from apps.administracion.models import AuditoriaEvento
from apps.hospitalizacion.models import HospitalAdmission
from apps.hospitalizacion.repositories.hospital_admission_repository import HospitalAdmissionRepository

# Campos de texto largo: se auditan como longitud (`<campo>_len`), nunca el
# contenido -- mismo criterio de minimizacion de datos que
# clinical_history_usecase._LONG_TEXT_FIELDS (no duplicar el motivo del
# ingreso en auditoria_eventos).
_LONG_TEXT_FIELDS = {"reason"}


def _field_snapshot(field_values):
    """`field_values`: dict {campo: valor}. Devuelve dict JSON-safe, con
    `<campo>_len` para los de texto largo."""
    snapshot = {}
    for field_name, value in field_values.items():
        if field_name in _LONG_TEXT_FIELDS:
            snapshot[f"{field_name}_len"] = len(value) if value else None
        else:
            snapshot[field_name] = value
    return snapshot


def update_admission(admission, *, fields, actor_id=None, change_reason=None, audit_hook):
    """Edicion humana de un `HospitalAdmission` -- SI versiona cuando pisa un
    valor ya cargado. `transaction.atomic()` vive aca (en el use-case), no en
    el repositorio -- mismo split que `clinical_history_usecase.py`.
    """
    with transaction.atomic():
        # Gotcha (documentado en clinical_history_usecase.py):
        # HospitalAdmissionRepository.update muta la instancia en memoria --
        # los valores previos se capturan ANTES de llamarlo.
        previous_values = {field_name: getattr(admission, field_name) for field_name in fields}
        datos_antes = _field_snapshot(previous_values)
        # Replica el mismo criterio de HospitalAdmissionRepository.update
        # para saber si esta llamada va a crear una HospitalAdmissionRevision
        # (solo cuando un campo YA tenia valor y se sobreescribe con otro).
        revision_created = any(
            previous_values[field_name] not in (None, "") and previous_values[field_name] != value
            for field_name, value in fields.items()
        )

        admission = HospitalAdmissionRepository.update(
            admission,
            fields=fields,
            updated_by_id=actor_id,
            change_reason=change_reason,
        )

        changed_fields = sorted(
            field_name
            for field_name, new_value in fields.items()
            if previous_values[field_name] != new_value
        )
        datos_despues = _field_snapshot(fields)
        datos_despues["changedFields"] = changed_fields
        datos_despues["revisionCreated"] = revision_created

        audit_hook(
            resource_id=admission.id,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
            strict=True,
        )

    return admission


def resolve_pending_fk(*, field, code_field, lookup, request_id=None):
    """Backfill diferido de una FK (`admitting_doctor`, `discharge_doctor` u
    `origin_center`) a partir de su codigo legado crudo. NO pasa por
    `HospitalAdmissionRepository.update()` -- por lo tanto NO genera
    `HospitalAdmissionRevision`. Queda igual loggeado como accion de SISTEMA
    en `AuditoriaEvento` (distinto de una edicion clinica/administrativa
    normal). Ver Engram, topic_key sdd/his-hospital-modelo-nom024/design,
    Decision 3.
    """
    with transaction.atomic():
        pending_qs = HospitalAdmission.objects.filter(**{
            f"{field}__isnull": True,
            f"{code_field}__isnull": False,
        })
        pending_count = pending_qs.count()

        resolved_count = HospitalAdmission.resolve_pending_fk(
            field=field, code_field=code_field, lookup=lookup,
        )

        AuditoriaEvento.objects.create(
            request_id=request_id or str(uuid.uuid4()),
            accion="hsp_admission.resolve_pending_fk",
            recurso_tipo="hospitalizacion",
            actor_nombre="Sistema",
            resultado=AuditoriaEvento.Resultado.SUCCESS,
            datos_antes={"pending": pending_count},
            datos_despues={
                "resolved": resolved_count,
                "field": field,
                "unmatched": pending_count - resolved_count,
            },
            meta={"module": "hospitalizacion", "codeField": code_field},
        )

    return resolved_count
