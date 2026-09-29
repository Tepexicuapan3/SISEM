"""
Importacion del modelo anterior (MySQL `dbclinicas`) a la historia clinica
unificada, fila por fila -- la usan `migrar_historial_clinico_legacy`
(his_clinica) y `migrar_historia_estomatologia_legacy` (his_clinicad).

Mapeo: seccion 7 del documento "Historia Clinica Unificada". Idempotente
por `legacy_ref` ("his_clinica:<no_hisclin>" / "his_clinicad:<no_hisclin>"):
si una fila ya se importo, sus registros derivados no se vuelven a crear.
Atencion con la inversion de his_clinicad: el significado lo define el
formulario, no el comentario del DDL -- SIN sufijo = familiar, CON sufijo
"p" = personal del paciente.
"""
import datetime

from django.db.models import Q

from apps.catalogos.models import CatCies, CatHabito
from apps.consulta_medica.models import (
    Allergy,
    FamilyHistory,
    Habit,
    HistoricalNote,
    LegacyVitalSigns,
    PersonalHistory,
    SpecialtySource,
    StomatologyHistory,
    SurgicalHistory,
)
from apps.consulta_medica.repositories.clinical_history_repository import ClinicalHistoryRepository
from apps.consulta_medica.services.legacy_migration_control_service import apply_patient_fields
from apps.consulta_medica.services.legacy_history_parsing import (
    format_legacy_vitals,
    is_negative_allergy,
    parse_legacy_vitals,
    split_allergy_items,
    split_annotations,
)

HIS_CLINICA_TEXT_COLUMNS = {
    "ds_antecedentes": HistoricalNote.Section.BACKGROUND,
    "ds_padecimiento": HistoricalNote.Section.CURRENT_ILLNESS,
    "ds_orgapasis": HistoricalNote.Section.SYSTEMS_REVIEW,
    "ds_cabeza": HistoricalNote.Section.HEAD,
    "ds_cuello": HistoricalNote.Section.NECK,
    "ds_torax": HistoricalNote.Section.CHEST,
    "ds_abdomen": HistoricalNote.Section.ABDOMEN,
    "ds_genitales": HistoricalNote.Section.GENITALS,
    "ds_miembros": HistoricalNote.Section.LIMBS,
    "ds_mdiagnostico": HistoricalNote.Section.DIAGNOSTIC_MANAGEMENT,
    "ds_mterapeutico": HistoricalNote.Section.THERAPEUTIC_MANAGEMENT,
    "ds_alergias": HistoricalNote.Section.ALLERGIES,
}

VITALS_COLUMNS = {
    "no_peso": "Peso",
    "no_talla": "Talla",
    "no_ta": "TA",
    "no_pulso": "Pulso",
    "no_temp": "Temperatura",
    "no_resp": "Respiracion",
}

# his_clinicad: casillas (valor 'S') -> (CIE-10 sugerido por el documento, etiqueta)
FAMILY_FLAG_COLUMNS = {
    "sw_diabetes": ("E14", "Diabetes mellitus"),
    "sw_cancer": ("C80", "Cancer"),
    "sw_presalta": ("I10", "Hipertension arterial"),
    "sw_presbaja": ("I95", "Hipotension arterial"),
}
PERSONAL_FLAG_COLUMNS = {
    "sw_diabetesp": ("E14", "Diabetes mellitus"),
    "sw_presaltap": ("I10", "Hipertension arterial"),
    "sw_presbajap": ("I95", "Hipotension arterial"),
    "sw_asma": ("J45", "Asma"),
    "sw_hepatitis": ("B19", "Hepatitis viral"),
    "sw_sida": ("B24", "VIH"),
}
HABIT_FLAG_COLUMNS = {
    "sw_tabaquismo": "tabaquismo",
    "sw_alcoholismo": "alcoholismo",
    "sw_toxicomias": "toxicomanias",
}
# Columna de his_clinicad -> CAT_TIPO_ALERGIA (1 medicamento, 2 anestesia,
# 3 material dental, 4 ambiental, 5 alimento, 9 otro).
DENTAL_ALLERGY_COLUMNS = {
    "ds_alemedicam": 1,
    "ds_alemdental": 3,
    "ds_aleanestes": 2,
    "ds_aleambient": 4,
    "ds_alealiment": 5,
    "ds_aleotros": 9,
}
OTHER_ALLERGY_TYPE = 9


def _flag(value):
    return (value or "").strip().upper() == "S"


def _text(value):
    return (str(value) if value is not None else "").strip()


class LegacyHistoryImporter:
    def __init__(self, run=None):
        # LegacyMigrationRun de la ejecucion (bitacora); los conflictos de la
        # ficha quedan ligados a ella.
        self.run = run
        self._cie_cache = {}
        self._habits = {habit.code: habit.id for habit in CatHabito.objects.all()}
        self.counters = {"notes": 0, "allergies": 0, "records": 0, "vitals": 0, "conflicts": 0}

    def patient_fields(self, patient, values, *, legacy_ref, legacy_date):
        """Ficha del paciente con la regla de conflictos del plan de migracion
        (ver legacy_migration_control_service)."""
        if isinstance(legacy_date, datetime.datetime):
            legacy_date = legacy_date.date()
        conflicts = apply_patient_fields(
            patient, values, legacy_ref=legacy_ref, legacy_date=legacy_date, run=self.run,
        )
        self.counters["conflicts"] += len(conflicts)

    def cie_code(self, category):
        if category not in self._cie_cache:
            self._cie_cache[category] = (
                CatCies.objects.filter(code=category).values_list("code", flat=True).first()
                or CatCies.objects.filter(code__startswith=category)
                .order_by("code").values_list("code", flat=True).first()
            )
        return self._cie_cache[category]

    @staticmethod
    def already_imported(ref):
        ref_filter = Q(legacy_ref=ref) | Q(legacy_ref__startswith=f"{ref}:")
        return (
            HistoricalNote.objects.filter(ref_filter).exists()
            or PersonalHistory.objects.filter(ref_filter).exists()
            or FamilyHistory.objects.filter(ref_filter).exists()
            or Habit.objects.filter(ref_filter).exists()
            or SurgicalHistory.objects.filter(ref_filter).exists()
            or LegacyVitalSigns.objects.filter(legacy_ref=ref).exists()
        )

    def note(self, *, no_exp, pk_num, specialty, section, text, ref, split=True):
        annotations = split_annotations(text) if split else ([(text.strip(), None, None)] if text and text.strip() else [])
        if not annotations:
            return annotations
        # NOTA_HISTORICA pertenece a la HISTORIA_CLINICA del paciente.
        history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
        for content, noted_on, author in annotations:
            HistoricalNote.objects.create(
                clinical_history=history,
                no_exp=no_exp, pk_num=pk_num, specialty=specialty, section=section,
                noted_on=noted_on, author=(author or None) and author[:100],
                content=content, legacy_ref=ref,
            )
            self.counters["notes"] += 1
        return annotations

    def record(self, model, base, **fields):
        """Registro permanente del paciente. Deduplica por paciente + contenido:
        26 pacientes tienen mas de una fila en his_clinicad (dump 2026-09-03)
        y cada una repetiria sus casillas (p. ej. "Diabetes mellitus"
        familiar). Cuenta tambien lo dado de baja: si alguien lo desactivo en
        SIRES, el legado no lo revive."""
        identity = {"no_exp": base["no_exp"], "pk_num": base["pk_num"], **fields}
        if model.objects.filter(**identity).exists():
            return None
        created = model.objects.create(**base, **fields)
        self.counters["records"] += 1
        return created

    def allergy(self, *, no_exp, pk_num, substance, allergy_type_id, source):
        substance = substance.strip()[:255]
        if not substance or is_negative_allergy(substance):
            return
        if Allergy.objects.filter(no_exp=no_exp, pk_num=pk_num, substance__iexact=substance).exists():
            return
        Allergy.objects.create(
            no_exp=no_exp, pk_num=pk_num, allergy_type_id=allergy_type_id, substance=substance,
            severity=Allergy.Severity.MODERATE, service_origin_code=Allergy.SERVICE_BY_SOURCE[source],
        )
        self.counters["allergies"] += 1

    def vitals(self, *, no_exp, pk_num, specialty, row, ref):
        """Documento: "signos vitales sin consulta, fecha desconocida" -> una
        fila numerica en LegacyVitalSigns (no smt_visit_vitals, que exige
        visita). Idempotente por `legacy_ref`."""
        text = format_legacy_vitals({label: row.get(column) for column, label in VITALS_COLUMNS.items()})
        if not text or LegacyVitalSigns.objects.filter(legacy_ref=ref).exists():
            return
        history, _ = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
        LegacyVitalSigns.objects.create(
            clinical_history=history, no_exp=no_exp, pk_num=pk_num, specialty=specialty,
            raw_text=text, legacy_ref=ref,
            **parse_legacy_vitals(
                weight=row.get("no_peso"), height=row.get("no_talla"), blood_pressure=row.get("no_ta"),
                pulse=row.get("no_pulso"), temperature=row.get("no_temp"), respiration=row.get("no_resp"),
            ),
        )
        self.counters["vitals"] += 1

    # ── his_clinica (medicina general) ──────────────────────────────────────

    def import_his_clinica_row(self, row, *, no_exp, pk_num):
        ref = f"his_clinica:{row.get('no_hisclin')}"
        if self.already_imported(ref):
            return False
        for column, section in HIS_CLINICA_TEXT_COLUMNS.items():
            annotations = self.note(
                no_exp=no_exp, pk_num=pk_num, specialty=SpecialtySource.GENERAL,
                section=section, text=row.get(column), ref=f"{ref}:{column}",
            )
            if column == "ds_alergias":
                # Documento: una fila por elemento separado por coma, tipo
                # "otro" hasta que alguien la clasifique.
                for content, _date, _author in annotations:
                    for item in split_allergy_items(content):
                        self.allergy(no_exp=no_exp, pk_num=pk_num, substance=item,
                                     allergy_type_id=OTHER_ALLERGY_TYPE, source=Allergy.Source.GENERAL)
        self.vitals(no_exp=no_exp, pk_num=pk_num, specialty=SpecialtySource.GENERAL, row=row, ref=ref)
        return True

    # ── his_clinicad (estomatologia) ────────────────────────────────────────

    def import_his_clinicad_row(self, row, *, no_exp, pk_num, catalog_ids):
        ref = f"his_clinicad:{row.get('no_hisclin')}"
        if self.already_imported(ref):
            return False

        # HISTORIA_CLINICA: si el paciente no tiene historia general se crea
        # (con su PACIENTE). Ocupacion/estado civil van a PACIENTE con la regla
        # del plan de migracion: gana el fe_hisclin mas reciente entre
        # his_clinica y his_clinicad, lo editado en SIRES nunca se pisa y toda
        # discrepancia queda en cns_conflicto_migracion.
        history, _ = ClinicalHistoryRepository.get_or_create_for_patient(
            no_exp, pk_num,
            opened_on=row.get("fe_hisclin"),
            clinic_code=row.get("cd_clinica"),
            doctor_code=_text(row.get("cd_medico")) or None,
        )
        self.patient_fields(history.patient, catalog_ids, legacy_ref=ref, legacy_date=row.get("fe_hisclin"))
        StomatologyHistory.objects.get_or_create(
            no_exp=no_exp, pk_num=pk_num, defaults={"clinical_history": history},
        )

        base = {"no_exp": no_exp, "pk_num": pk_num, "source": SpecialtySource.LEGACY, "legacy_ref": ref}

        for column, (category, label) in FAMILY_FLAG_COLUMNS.items():
            if _flag(row.get(column)):
                self.record(FamilyHistory, base, cie_id=self.cie_code(category), description=label)
        if _text(row.get("ds_muerte")):
            self.record(
                FamilyHistory, base, is_deceased=True, cause_of_death=_text(row.get("ds_muerte"))[:255],
                description="Familiar finado",
            )

        for column, (category, label) in PERSONAL_FLAG_COLUMNS.items():
            if _flag(row.get(column)):
                self.record(PersonalHistory, base, cie_id=self.cie_code(category), description=label)

        for column, habit_code in HABIT_FLAG_COLUMNS.items():
            if _flag(row.get(column)):
                self.record(Habit, base, habit_id=self._habits[habit_code])
        if _text(row.get("ds_habitos")):
            self.record(Habit, base, habit_id=self._habits["otro"], notes=_text(row.get("ds_habitos")))
        if _text(row.get("ds_alimentos")):
            self.record(Habit, base, habit_id=self._habits["alimentacion"], notes=_text(row.get("ds_alimentos")))

        if _text(row.get("ds_antquir")):
            self.record(SurgicalHistory, base, procedure=_text(row.get("ds_antquir"))[:500])

        self.note(no_exp=no_exp, pk_num=pk_num, specialty=SpecialtySource.STOMATOLOGY,
                  section=HistoricalNote.Section.BACKGROUND, text=row.get("ds_antecedentes"),
                  ref=f"{ref}:ds_antecedentes")
        self.note(no_exp=no_exp, pk_num=pk_num, specialty=SpecialtySource.STOMATOLOGY,
                  section=HistoricalNote.Section.CURRENT_ILLNESS, text=row.get("ds_terapias"),
                  ref=f"{ref}:ds_terapias")

        for column, allergy_type_id in DENTAL_ALLERGY_COLUMNS.items():
            text = _text(row.get(column))
            if text:
                self.allergy(no_exp=no_exp, pk_num=pk_num, substance=text,
                             allergy_type_id=allergy_type_id, source=Allergy.Source.STOMATOLOGY)

        self.vitals(no_exp=no_exp, pk_num=pk_num, specialty=SpecialtySource.STOMATOLOGY, row=row, ref=ref)
        return True
