from django.db import transaction

from apps.consulta_medica.odontogram_constants import (
    ALL_TEETH_FDI,
    DECIDUOUS_TEETH_FDI,
    PERMANENT_TEETH_FDI,
)
from apps.consulta_medica.repositories.odontogram_repository import OdontogramRepository
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

from .consultation_usecase import ensure_doctor_role

_DENTITION_SETS = {
    "permanent": PERMANENT_TEETH_FDI,
    "deciduous": DECIDUOUS_TEETH_FDI,
    "all": ALL_TEETH_FDI,
}

HEALTHY_CODE = "healthy"


def _validation_error(field, message):
    return VisitDomainError(
        "VALIDATION_ERROR", "Hay errores en el formulario", 422, details={field: [message]},
    )


def _state_contract(state):
    return {
        "condition": state.state.code,
        "notes": state.observation,
    }


def get_patient_odontogram(
    no_exp, pk_num, roles, permissions=None, *, dentition="permanent", version_id=None,
):
    """
    Odontograma de la ULTIMA version (o de `version_id`). Mismo contrato de
    `items` que antes (una entrada por pieza, "healthy" si no tiene
    registro) mas `faces` por pieza, la version y el CPOD.
    """
    ensure_doctor_role(roles, permissions)

    tooth_fdi_list = _DENTITION_SETS.get(dentition)
    if tooth_fdi_list is None:
        raise _validation_error("dentition", "Debe ser 'permanent', 'deciduous' o 'all'.")

    if version_id is not None:
        odontogram = OdontogramRepository.get_version(no_exp, pk_num, version_id)
        if odontogram is None:
            raise VisitDomainError("ODONTOGRAM_VERSION_NOT_FOUND", "Version de odontograma no encontrada.", 404)
    else:
        odontogram = OdontogramRepository.latest_for_patient(no_exp, pk_num)

    states = OdontogramRepository.states_by_tooth(odontogram)
    updated_at = odontogram.created_at if odontogram else None

    items = []
    for tooth_fdi in tooth_fdi_list:
        tooth_states = states.get(tooth_fdi, {})
        whole = tooth_states.get("")
        items.append({
            "toothFdi": tooth_fdi,
            "condition": whole.state.code if whole else HEALTHY_CODE,
            "notes": whole.observation if whole else None,
            "updatedAt": updated_at if whole else None,
            "faces": [
                {"face": face, **_state_contract(state)}
                for face, state in sorted(tooth_states.items())
                if face
            ],
        })

    return {
        "items": items,
        "version": OdontogramRepository.version_contract(odontogram) if odontogram else None,
    }


def list_odontogram_versions(no_exp, pk_num, roles, permissions=None):
    ensure_doctor_role(roles, permissions)
    return {
        "items": [
            OdontogramRepository.version_contract(version)
            for version in OdontogramRepository.list_versions(no_exp, pk_num)
        ]
    }


def upsert_tooth_condition(
    no_exp,
    pk_num,
    tooth_fdi,
    roles,
    *,
    condition,
    notes,
    actor_id,
    face="",
    visit_id=None,
    permissions=None,
    audit_hook,
):
    ensure_doctor_role(roles, permissions)

    if tooth_fdi not in ALL_TEETH_FDI:
        raise _validation_error("toothFdi", "Numero de pieza FDI invalido.")

    state = OdontogramRepository.active_state_by_code(condition)
    if state is None:
        raise _validation_error("condition", "Condicion invalida.")

    if visit_id is not None and not Visit.objects.filter(
        id_visit=visit_id, no_exp=no_exp,
    ).exists():
        raise _validation_error("visitId", "La visita no existe o no es de este paciente.")

    face = face or ""

    with transaction.atomic():
        odontogram = OdontogramRepository.version_for_change(
            no_exp=no_exp, pk_num=pk_num, visit_id=visit_id, actor_id=actor_id,
        )
        previous = OdontogramRepository.states_by_tooth(odontogram).get(tooth_fdi, {}).get(face)
        datos_antes = {
            "condition": previous.state.code if previous else None,
            "notesLen": len(previous.observation) if previous and previous.observation else None,
        }

        tooth_state = OdontogramRepository.upsert_state(
            odontogram, tooth_fdi=tooth_fdi, face=face, state=state, observation=notes,
        )
        OdontogramRepository.recompute(odontogram)

        audit_hook(
            resource_id=odontogram.id_odontogram,
            datos_antes=datos_antes,
            datos_despues={
                "toothFdi": tooth_fdi,
                "face": face,
                "condition": state.code,
                "notesLen": len(notes) if notes else None,
                "versionId": odontogram.id_odontogram,
                "dmftIndex": odontogram.dmft_index,
            },
            strict=True,
        )

    return {
        "toothFdi": tooth_fdi,
        "face": face,
        **_state_contract(tooth_state),
        "updatedAt": odontogram.created_at,
        "version": OdontogramRepository.version_contract(odontogram),
    }
