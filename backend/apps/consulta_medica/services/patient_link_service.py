"""
Paso 7 del 5.1 (documento "Historia Clinica Unificada"): las tablas clinicas
apuntan al paciente (id_paciente) en lugar de identificarlo por no_exp + pk_num.

Etapas:
  7a  columna id_paciente que admite NULL (migracion 0044).
  7b  vincular lo que ya existe: comando vincular_id_paciente.
  7c  escritura doble: al guardar un registro sin paciente, se resuelve aqui
      (senal pre_save). OJO: queryset.update() y bulk_create() no disparan
      senales; despues de una importacion masiva hay que volver a correr 7b.
  7d  lecturas por id_paciente: for_patient(). Las importaciones del legado,
      la correccion de llaves y el propio vinculo siguen trabajando por llave
      a proposito.
  7e  NOT NULL (pendiente, cuando 7b reporte cero filas sin paciente).
"""
from __future__ import annotations

from django.apps import apps
from django.db.models import Q
from django.db.models.signals import pre_save

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


def keys_for_person(no_exp, pk_num) -> list[tuple]:
    """Llaves (no_exp, pk_num) de todos los registros de la persona, incluida
    la pedida. Para tablas que todavia no tienen id_paciente (visitas)."""
    keys = {(no_exp, pk_num)}
    keys.update(_record_key(record) for record in records_for_key(no_exp, pk_num))
    return sorted(keys, key=str)


def for_patient(queryset, no_exp, pk_num):
    """
    7d + Fase 4 del plan identidad: filas clinicas de la PERSONA (todas sus
    afiliaciones), leidas por id_paciente. Hoy da exactamente lo mismo que
    antes porque cada persona tiene un solo registro.

    Transitorio hasta 7e (NOT NULL): incluye ademas las filas de esas llaves
    que todavia no tienen id_paciente, para que ninguna pantalla pierda datos
    mientras vincular_id_paciente no haya corrido.
    """
    unlinked = Q(patient__isnull=True, no_exp=no_exp, pk_num=pk_num)
    records = records_for_key(no_exp, pk_num)
    if not records:
        return queryset.filter(unlinked)
    condition = Q(patient__in=records) | unlinked
    for record_no_exp, record_key in {_record_key(record) for record in records}:
        condition |= Q(patient__isnull=True, no_exp=record_no_exp, pk_num=record_key)
    return queryset.filter(condition)


def linked_models():
    """Modelos de consulta_medica con llave de paciente y FK id_paciente."""
    result = []
    for model in apps.get_app_config("consulta_medica").get_models():
        fields = {f.name: f for f in model._meta.concrete_fields}
        patient_field = fields.get("patient")
        if (
            patient_field is not None
            and patient_field.is_relation
            and patient_field.related_model is Patient
            and {"no_exp", "pk_num"} <= fields.keys()
        ):
            result.append(model)
    return result


def _link_on_save(sender, instance, **kwargs):
    from apps.consulta_medica.services.operational_link_service import (
        SIN_LLAVE, congelar_llave, paciente_de_la_visita, resolve_record,
    )

    if instance.patient_id is None and instance.no_exp:
        if sender._meta.label in SIN_LLAVE:
            # Plan contraer la llave vieja: la fila solo guarda id_paciente; si el
            # registro no existe se abre por la puerta central (como las operativas).
            patient = resolve_record(sender, instance.no_exp, instance.pk_num,
                                     created_by_id=getattr(instance, "created_by_id", None))
        else:
            patient = find_patient_by_record_key(instance.no_exp, instance.pk_num)
        if patient is not None:
            instance.patient = patient
    if instance.patient_id is None and sender._meta.label in SIN_LLAVE:
        instance.patient_id = paciente_de_la_visita(instance)
    congelar_llave(sender, instance)


def connect_signals():
    for model in linked_models():
        pre_save.connect(_link_on_save, sender=model, dispatch_uid=f"link_patient_{model._meta.label}")


def link_existing(*, dry_run=False, create_missing=True, progress=None) -> dict[str, dict[str, int]]:
    """
    7b: llena id_paciente donde falta. Si no existe el paciente de una llave y
    create_missing es True, lo crea (como al abrir su historia), para que ningun
    registro quede sin paciente antes del NOT NULL.
    Devuelve {tabla: {"rows": vinculadas, "patients_created": n, "unresolved": llaves}}.
    """
    # Import diferido: el repositorio usa find_patient_by_record_key de este modulo.
    from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
    from apps.consulta_medica.services.operational_link_service import (
        creates_record, no_exp_field, operational_models,
    )
    from apps.consulta_medica.services.patient_registry_service import ORIGEN_REGULARIZACION

    report: dict[str, dict[str, int]] = {}
    # Tablas clinicas (7b) y operativas (plan identidad, Fase 5).
    for model in linked_models() + operational_models():
        create_for_model = create_missing and creates_record(model)
        campo = no_exp_field(model)
        stats = {"rows": 0, "patients_created": 0, "unresolved": 0}
        keys = list(
            model.objects.filter(patient__isnull=True)
            .values_list(campo, "pk_num").distinct()
        )
        for index, (no_exp, pk_num) in enumerate(keys, start=1):
            if pk_num is None:
                # Sin pk_num no hay llave que resolver (p. ej. un recien nacido
                # provisional de la Fase 6 ya nace con su id_paciente).
                stats["unresolved"] += 1
                continue
            pending = model.objects.filter(**{campo: no_exp}, pk_num=pk_num, patient__isnull=True)
            patient = find_patient_by_record_key(no_exp, pk_num)
            if patient is None and create_for_model and not dry_run:
                # Regularizacion: los registros clinicos ya existen; no se
                # verifica en SERMED (ver patient_registry_service).
                patient, created = PatientRepository.get_or_create(
                    no_exp, pk_num, origen=ORIGEN_REGULARIZACION,
                )
                stats["patients_created"] += int(created)
            if patient is None:
                if dry_run and create_for_model:
                    stats["patients_created"] += 1
                    stats["rows"] += pending.count()
                else:
                    stats["unresolved"] += 1
                continue
            stats["rows"] += pending.count() if dry_run else pending.update(patient=patient)
            if progress and index % 1000 == 0:
                progress(model._meta.db_table, index, len(keys))
        report[model._meta.db_table] = stats
    return report


def unlinked_counts() -> dict[str, int]:
    """Filas sin id_paciente por tabla (tiene que dar cero antes del NOT NULL)."""
    from apps.consulta_medica.services.operational_link_service import operational_models

    return {
        model._meta.db_table: model.objects.filter(patient__isnull=True).count()
        for model in linked_models() + operational_models()
    }
