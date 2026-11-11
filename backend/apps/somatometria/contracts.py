"""
Contrato de lectura de somatometria para otros dominios (hoy: el control de
cronicos de padrones). Devuelve valores planos; nadie fuera de este dominio
lee smt_visit_vitals.
"""


def vitals_for_visit(visit_id) -> dict | None:
    """Signos vitales de la visita, o None si no se capturaron."""
    from apps.somatometria.repositories.vitals_repository import VitalsRepository

    vitals = VitalsRepository.get_vitals_by_visit_id(visit_id)
    if vitals is None:
        return None
    return {
        "captured_at": vitals.fch_alta,
        "weight_kg": vitals.weight_kg,
        "bmi": vitals.bmi,
        "waist_circumference_cm": vitals.waist_circumference_cm,
        "blood_pressure_systolic": vitals.blood_pressure_systolic,
        "blood_pressure_diastolic": vitals.blood_pressure_diastolic,
        "glucosa_capilar_mgdl": vitals.glucosa_capilar_mgdl,
    }
