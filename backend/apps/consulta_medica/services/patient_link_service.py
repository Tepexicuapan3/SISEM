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
    registros conservan el cd_familiar como llave (legacy_family_map).
    """
    patient = Patient.objects.filter(no_exp=no_exp, pk_num=pk_num).first()
    if patient is None and pk_num:
        patient = Patient.objects.filter(
            no_exp=no_exp, pk_num__isnull=True, legacy_family_code=pk_num,
        ).first()
    return patient


def for_patient(queryset, no_exp, pk_num):
    """
    7d: registros de un paciente leidos por id_paciente. Asi tambien aparecen
    los que cuelgan del paciente con otra llave (familiar sin PK_NUM, y mas
    adelante pacientes fusionados).

    Transitorio hasta 7e (NOT NULL): incluye ademas las filas de esa llave que
    todavia no tienen id_paciente, para que ninguna pantalla pierda datos
    mientras vincular_id_paciente no haya corrido.
    """
    unlinked = Q(patient__isnull=True, no_exp=no_exp, pk_num=pk_num)
    patient = find_patient_by_record_key(no_exp, pk_num)
    if patient is None:
        return queryset.filter(unlinked)
    return queryset.filter(Q(patient=patient) | unlinked)


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
    if instance.patient_id is None and instance.no_exp:
        patient = find_patient_by_record_key(instance.no_exp, instance.pk_num)
        if patient is not None:
            instance.patient = patient


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
    from apps.consulta_medica.services.patient_registry_service import ORIGEN_REGULARIZACION

    report: dict[str, dict[str, int]] = {}
    for model in linked_models():
        stats = {"rows": 0, "patients_created": 0, "unresolved": 0}
        keys = list(
            model.objects.filter(patient__isnull=True)
            .values_list("no_exp", "pk_num").distinct()
        )
        for index, (no_exp, pk_num) in enumerate(keys, start=1):
            pending = model.objects.filter(no_exp=no_exp, pk_num=pk_num, patient__isnull=True)
            patient = find_patient_by_record_key(no_exp, pk_num)
            if patient is None and create_missing and not dry_run:
                # Regularizacion: los registros clinicos ya existen; no se
                # verifica en SERMED (ver patient_registry_service).
                patient, created = PatientRepository.get_or_create(
                    no_exp, pk_num, origen=ORIGEN_REGULARIZACION,
                )
                stats["patients_created"] += int(created)
            if patient is None:
                if dry_run and create_missing:
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
    return {model._meta.db_table: model.objects.filter(patient__isnull=True).count() for model in linked_models()}
