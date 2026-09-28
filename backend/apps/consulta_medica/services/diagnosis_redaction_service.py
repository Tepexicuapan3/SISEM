"""
Redaccion de diagnosticos CIE-10 sensibles (VIH, salud mental, consumo de
sustancias) hacia clientes sin el permiso requerido -- change
`diagnosticos-sensibles`.

Decision del usuario: se redacta SOLO el diagnostico (codigo CIE-10 +
descripcion + el texto de diagnostico ligado deterministicamente a ese
codigo -- `primaryDiagnosis` de una consulta, `notes` de un diagnostico
secundario), NUNCA el registro completo -- fecha, medico, notas SOAP del
resto de la consulta se sirven normal. Solo cubre diagnosticos CODIFICADOS
en CIE-10 (`CatCies`); campos de texto libre sin CIE asociado
(`current_illness`, `diagnostic_management` de ClinicalHistory) no se
pueden clasificar de forma confiable sin NLP -- fuera de alcance, igual que
el documento fuente de este change lo deja pendiente.
"""

from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.catalogos.services.sensitive_diagnosis_service import classify_cie

REDACTED_DESCRIPTION = "Diagnóstico restringido"
REDACTED_TEXT = "Información restringida"


def _has_permission(required_permission, permissions):
    permission_state = evaluate_permission_requirement(
        {"allOf": [required_permission]}, permissions or [],
    )
    return permission_state["granted"]


def redact_cie_if_restricted(*, code, description, permissions, linked_text=None):
    """
    Si `code` cae en un rango CIE-10 sensible y el actor (via `permissions`)
    no tiene el `required_permission` de ese rango, devuelve una tupla
    `(code, description, linked_text, restricted)` con `code=None`,
    `description`/`linked_text` reemplazados por un marcador -- si no es
    sensible o el actor SI tiene permiso, devuelve los valores originales
    sin tocar.

    `linked_text` es opcional: el texto de diagnostico deterministicamente
    ligado a este CIE (ej. `primaryDiagnosis` de la consulta, `notes` del
    diagnostico secundario) -- se redacta junto con `description` porque
    dejarlo visible volveria trivial esquivar la redaccion (el medico
    escribe el mismo diagnostico en texto libre al lado del codigo).
    """
    if not code:
        return code, description, linked_text, False

    classification = classify_cie(code)
    if classification is None:
        return code, description, linked_text, False

    _category, required_permission = classification
    if _has_permission(required_permission, permissions):
        return code, description, linked_text, False

    redacted_linked_text = REDACTED_TEXT if linked_text else linked_text
    return None, REDACTED_DESCRIPTION, redacted_linked_text, True
