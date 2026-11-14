"""
Contrato de lectura: miembros vigentes de un expediente (titular y
derechohabientes) para que otro dominio elija a la persona sin escribir el
pkNum a mano (docs/plans/cronicos-alta-padron.md).

Reusa lookup_patient de la busqueda de recepcion, sin fotos y solo con los
datos para identificar a la persona: ni foto ni consultorio familiar. Los
errores (404 expediente, 503 SERMED) se propagan como VisitDomainError.
"""

FIELDS = ("idPaciente", "noExp", "pkNum", "nombre", "parentesco", "edad", "fechaNac")


def family_members(no_exp):
    from apps.recepcion.uses_case.visit_queue_usecase import lookup_patient

    result = lookup_patient((no_exp or "").strip(), historico=False, incluir_fotos=False)
    members = [result.get("titular"), *result.get("dependientes", [])]
    return [{field: member.get(field) for field in FIELDS} for member in members if member]
