"""
Paso 7 del 5.1 (documento "Historia Clinica Unificada"): las tablas clinicas
apuntan al paciente (id_paciente) en lugar de identificarlo por no_exp + pk_num.

Hecho: id_paciente (7a), vinculo de lo existente (7b), escritura doble (7c),
lecturas por id_paciente (7d) y NOT NULL (7e, C6 del plan contraer la llave
vieja). En C7 se borraron no_exp/pk_num de esas tablas y se retiraron el
vinculo masivo (vincular_id_paciente) y la escritura doble. Aqui queda la
resolucion de una llave que escribe el usuario (expediente + pkNum) a sus
registros de cns_paciente.
"""
from __future__ import annotations

from django.db.models import Q

from apps.consulta_medica.models import Patient


def find_patient_by_record_key(no_exp, pk_num) -> Patient | None:
    """
    Paciente de un registro identificado por (no_exp, pk_num). Transitorio:
    un familiar del legado sin PK_NUM tiene pk_num NULL en cns_paciente y sus
    registros conservan el cd_familiar como llave (legacy_family_map). Igual
    el recien nacido provisional con su cd_provisional.
    """
    patient = Patient.objects.filter(no_exp=no_exp, pk_num=pk_num).first()
    if patient is None and pk_num:
        patient = Patient.objects.filter(
            Q(legacy_family_code=pk_num) | Q(provisional_code=pk_num), no_exp=no_exp, pk_num__isnull=True,
        ).first()
    return patient


def _record_key(patient: Patient) -> tuple:
    """Llave con la que sus filas clinicas identifican a un registro: el
    familiar del legado sin PK_NUM usa su cd_familiar como pk_num, y el
    provisional su cd_provisional."""
    if patient.pk_num is not None:
        return patient.no_exp, patient.pk_num
    if patient.legacy_family_code is not None:
        return patient.no_exp, patient.legacy_family_code
    return patient.no_exp, patient.provisional_code


def records_for_key(no_exp, pk_num) -> list[Patient]:
    """
    Plan identidad, Fase 4: todos los registros (afiliaciones) de la PERSONA
    a la que pertenece esta llave, incluido el propio. Hoy cada persona tiene
    un solo registro; con la vinculacion (Fase 7) aparecen los demas (como
    hijo, como trabajador, como recien nacido).
    """
    patient = find_patient_by_record_key(no_exp, pk_num)
    if patient is None:
        return []
    return list(Patient.objects.filter(person_id=patient.person_id).order_by("id_patient"))


def for_patient(queryset, no_exp, pk_num):
    """
    7d + Fase 4 del plan identidad: filas clinicas de la PERSONA (todas sus
    afiliaciones), leidas por id_paciente.

    Las tablas que todavia guardan la llave (archivo del legado) incluyen
    ademas sus filas sin id_paciente de las llaves de esa persona. Las tablas
    de atencion ya no tienen llave (plan contraer la llave vieja, C7).
    """
    con_llave = "no_exp" in {f.name for f in queryset.model._meta.concrete_fields}
    records = records_for_key(no_exp, pk_num)
    if not con_llave:
        return queryset.filter(patient__in=records) if records else queryset.none()
    unlinked = Q(patient__isnull=True, no_exp=no_exp, pk_num=pk_num)
    if not records:
        return queryset.filter(unlinked)
    condition = Q(patient__in=records) | unlinked
    for record_no_exp, record_key in {_record_key(record) for record in records}:
        condition |= Q(patient__isnull=True, no_exp=record_no_exp, pk_num=record_key)
    return queryset.filter(condition)
