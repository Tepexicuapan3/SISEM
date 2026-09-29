"""
Migracion de DATOS de la historia clinica unificada (seccion 7 "Mapeo campo
por campo" del documento). Mueve TODO lo que la migracion 0030 va a borrar
a su lugar nuevo -- ninguna columna se elimina sin destino:

  ClinicalHistory (texto acumulado)   -> HistoricalNote (una por anotacion,
                                         fecha/usuario recuperados de la firma)
  ClinicalHistory.allergies           -> Allergy (una por elemento, "otro")
                                         + HistoricalNote con el texto original
  StomatologyHistory casillas         -> FamilyHistory / PersonalHistory / Habit
  StomatologyHistory textos           -> Habit / SurgicalHistory / PersonalHistory
                                         / HistoricalNote
  StomatologyHistory.allergy_*        -> Allergy con su categoria
  *Revision.previous_* (lo que se va) -> HistoricalNote origen "revision"
  OdontogramTooth                     -> Odontogram (version "migrado") +
                                         OdontogramToothState, con CPOD
  Allergy.is_active=False             -> status "entered_in_error"

Corre dentro de la transaccion de la migracion (Postgres): o se aplica
todo, o nada.
"""
from django.db import migrations
from django.db.models import Max

from apps.consulta_medica.services.legacy_history_parsing import (
    is_negative_allergy,
    split_allergy_items,
    split_annotations,
)

GENERAL = "general"
STOMATOLOGY = "stomatology"
LEGACY = "legacy"

# ClinicalHistory: campo de texto -> apartado de HistoricalNote.
CLINICAL_TEXT_FIELDS = {
    "family_history": "antecedentes",
    "current_illness": "padecimiento",
    "systems_review": "aparatos_sistemas",
    "head_exam": "cabeza",
    "neck_exam": "cuello",
    "chest_exam": "torax",
    "abdomen_exam": "abdomen",
    "genitals_exam": "genitales",
    "limbs_exam": "miembros",
    "diagnostic_management": "manejo_diagnostico",
    "therapeutic_management": "manejo_terapeutico",
    "allergies": "alergias",
}

# Equivalencias CIE-10 del documento (a validar por el area medica).
FAMILY_FLAGS = {
    "family_diabetes": ("E14", "Diabetes mellitus"),
    "family_cancer": ("C80", "Cancer"),
    "family_high_blood_pressure": ("I10", "Hipertension arterial"),
    "family_low_blood_pressure": ("I95", "Hipotension arterial"),
}
PERSONAL_FLAGS = {
    "personal_diabetes": ("E14", "Diabetes mellitus"),
    "personal_asthma": ("J45", "Asma"),
    "personal_high_blood_pressure": ("I10", "Hipertension arterial"),
    "personal_low_blood_pressure": ("I95", "Hipotension arterial"),
    "personal_hepatitis": ("B19", "Hepatitis viral"),
    "personal_hiv": ("B24", "VIH"),
}
HABIT_FLAGS = {
    "personal_smoking": "tabaquismo",
    "personal_alcoholism": "alcoholismo",
    "personal_substance_abuse": "toxicomanias",
}
STOMATOLOGY_ALLERGY_FIELDS = {
    "allergy_medications": "medication",
    "allergy_dental_material": "dental_material",
    "allergy_anesthesia": "anesthesia",
    "allergy_food": "food",
    "allergy_environment": "environmental",
    "allergy_other": "other",
}
STOMATOLOGY_REVISION_TEXT_FIELDS = {
    "cause_of_death": "antecedentes",
    "habits": "habitos",
    "diet": "habitos",
    "surgical_history": "quirurgicos",
    "traumatic_history": "traumaticos",
    "current_illness_history": "padecimiento",
}
FLAG_LABELS = {
    **{field: f"{label} (familiar)" for field, (_c, label) in FAMILY_FLAGS.items()},
    **{field: f"{label} (personal)" for field, (_c, label) in PERSONAL_FLAGS.items()},
    "personal_smoking": "Tabaquismo",
    "personal_alcoholism": "Alcoholismo",
    "personal_substance_abuse": "Toxicomanias",
}


class _Ctx:
    def __init__(self, apps):
        self.CatCies = apps.get_model("catalogos", "CatCies")
        self.CatHabito = apps.get_model("catalogos", "CatHabito")
        self.CatEstadoPieza = apps.get_model("catalogos", "CatEstadoPieza")
        self.Allergy = apps.get_model("consulta_medica", "Allergy")
        self.HistoricalNote = apps.get_model("consulta_medica", "HistoricalNote")
        self.PersonalHistory = apps.get_model("consulta_medica", "PersonalHistory")
        self.FamilyHistory = apps.get_model("consulta_medica", "FamilyHistory")
        self.SurgicalHistory = apps.get_model("consulta_medica", "SurgicalHistory")
        self.Habit = apps.get_model("consulta_medica", "Habit")
        self._cie_cache = {}
        self._habit_cache = {}

    def cie_code(self, code):
        """Codigo real de CatCies para una categoria CIE-10 (ej. E14 -> E14
        o su primer subcodigo E140/E149). None si el catalogo no lo tiene."""
        if code not in self._cie_cache:
            match = (
                self.CatCies.objects.filter(code=code).values_list("code", flat=True).first()
                or self.CatCies.objects.filter(code__startswith=code)
                .order_by("code").values_list("code", flat=True).first()
            )
            self._cie_cache[code] = match
        return self._cie_cache[code]

    def habit_id(self, code):
        if code not in self._habit_cache:
            self._habit_cache[code] = self.CatHabito.objects.get(code=code).id
        return self._habit_cache[code]

    def add_note(self, *, no_exp, pk_num, specialty, section, content, noted_on=None,
                 author=None, origin="legacy_text", legacy_ref=None):
        content = (content or "").strip()
        if not content:
            return
        self.HistoricalNote.objects.create(
            no_exp=no_exp, pk_num=pk_num, specialty=specialty, section=section,
            noted_on=noted_on, author=(author or None) and author[:100],
            content=content, origin=origin, legacy_ref=legacy_ref,
        )

    def add_allergy(self, *, no_exp, pk_num, substance, category, source, created_by_id):
        substance = substance.strip()[:255]
        if not substance or is_negative_allergy(substance):
            return
        exists = self.Allergy.objects.filter(
            no_exp=no_exp, pk_num=pk_num, substance__iexact=substance,
        ).exists()
        if not exists:
            self.Allergy.objects.create(
                no_exp=no_exp, pk_num=pk_num, category=category, substance=substance,
                severity="moderate", source=source, created_by_id=created_by_id,
            )


def _migrate_clinical_history(ctx, apps):
    ClinicalHistory = apps.get_model("consulta_medica", "ClinicalHistory")
    for history in ClinicalHistory.objects.all().iterator():
        ref = f"cns_clinical_history:{history.id_clinical_history}"
        for field, section in CLINICAL_TEXT_FIELDS.items():
            text = getattr(history, field)
            for content, noted_on, author in split_annotations(text):
                ctx.add_note(
                    no_exp=history.no_exp, pk_num=history.pk_num, specialty=GENERAL,
                    section=section, content=content, noted_on=noted_on, author=author,
                    legacy_ref=f"{ref}:{field}",
                )
                if field == "allergies":
                    # Si `migrar_alergias_estructuradas` ya corrio, existe una
                    # Allergy con el texto completo -- add_allergy no duplica.
                    for item in split_allergy_items(content):
                        ctx.add_allergy(
                            no_exp=history.no_exp, pk_num=history.pk_num, substance=item,
                            category="other", source=GENERAL, created_by_id=history.created_by_id,
                        )


def _migrate_stomatology_history(ctx, apps):
    StomatologyHistory = apps.get_model("consulta_medica", "StomatologyHistory")
    for history in StomatologyHistory.objects.all().iterator():
        ref = f"cns_stomatology_history:{history.id_stomatology_history}"
        base = {
            "no_exp": history.no_exp, "pk_num": history.pk_num, "source": STOMATOLOGY,
            "legacy_ref": ref, "created_by_id": history.created_by_id,
        }

        for field, (code, label) in FAMILY_FLAGS.items():
            if getattr(history, field):
                ctx.FamilyHistory.objects.create(**base, cie_id=ctx.cie_code(code), description=label)
        if (history.cause_of_death or "").strip():
            ctx.FamilyHistory.objects.create(
                **base, is_deceased=True, cause_of_death=history.cause_of_death.strip()[:255],
                description="Familiar finado",
            )

        for field, (code, label) in PERSONAL_FLAGS.items():
            if getattr(history, field):
                ctx.PersonalHistory.objects.create(**base, cie_id=ctx.cie_code(code), description=label)
        if (history.traumatic_history or "").strip():
            text = history.traumatic_history.strip()
            ctx.PersonalHistory.objects.create(**base, description=f"Traumatico: {text}"[:500])
            if len(text) > 480:
                ctx.add_note(no_exp=history.no_exp, pk_num=history.pk_num, specialty=STOMATOLOGY,
                             section="traumaticos", content=text, legacy_ref=ref)

        for field, habit_code in HABIT_FLAGS.items():
            if getattr(history, field):
                ctx.Habit.objects.create(**base, habit_id=ctx.habit_id(habit_code))
        if (history.habits or "").strip():
            ctx.Habit.objects.create(**base, habit_id=ctx.habit_id("otro"), notes=history.habits.strip())
        if (history.diet or "").strip():
            ctx.Habit.objects.create(**base, habit_id=ctx.habit_id("alimentacion"), notes=history.diet.strip())

        if (history.surgical_history or "").strip():
            text = history.surgical_history.strip()
            ctx.SurgicalHistory.objects.create(**base, procedure=text[:500])
            if len(text) > 500:
                ctx.add_note(no_exp=history.no_exp, pk_num=history.pk_num, specialty=STOMATOLOGY,
                             section="quirurgicos", content=text, legacy_ref=ref)

        ctx.add_note(no_exp=history.no_exp, pk_num=history.pk_num, specialty=STOMATOLOGY,
                     section="padecimiento", content=history.current_illness_history, legacy_ref=ref)

        for field, category in STOMATOLOGY_ALLERGY_FIELDS.items():
            text = getattr(history, field)
            if (text or "").strip():
                ctx.add_note(no_exp=history.no_exp, pk_num=history.pk_num, specialty=STOMATOLOGY,
                             section="alergias", content=text, legacy_ref=f"{ref}:{field}")
                if not is_negative_allergy(text):
                    ctx.add_allergy(no_exp=history.no_exp, pk_num=history.pk_num, substance=text,
                                    category=category, source=STOMATOLOGY,
                                    created_by_id=history.created_by_id)


def _migrate_revisions(ctx, apps):
    ClinicalHistoryRevision = apps.get_model("consulta_medica", "ClinicalHistoryRevision")
    for revision in ClinicalHistoryRevision.objects.select_related("history").iterator():
        history = revision.history
        author = f"usuario #{revision.changed_by_id}" if revision.changed_by_id else None
        for field, section in CLINICAL_TEXT_FIELDS.items():
            ctx.add_note(
                no_exp=history.no_exp, pk_num=history.pk_num, specialty=GENERAL, section=section,
                content=getattr(revision, f"previous_{field}"), noted_on=revision.changed_at.date(),
                author=author, origin="revision",
                legacy_ref=f"cns_clinical_history_revision:{revision.pk}:{field}",
            )

    StomatologyHistoryRevision = apps.get_model("consulta_medica", "StomatologyHistoryRevision")
    for revision in StomatologyHistoryRevision.objects.select_related("history").iterator():
        history = revision.history
        author = f"usuario #{revision.changed_by_id}" if revision.changed_by_id else None
        common = {
            "no_exp": history.no_exp, "pk_num": history.pk_num, "specialty": STOMATOLOGY,
            "noted_on": revision.changed_at.date(), "author": author, "origin": "revision",
            "legacy_ref": f"cns_stomatology_history_revision:{revision.pk}",
        }
        flags = [label for field, label in FLAG_LABELS.items() if getattr(revision, f"previous_{field}")]
        if flags:
            ctx.add_note(**common, section="antecedentes", content="Casillas marcadas: " + ", ".join(flags))
        for field, section in STOMATOLOGY_REVISION_TEXT_FIELDS.items():
            ctx.add_note(**common, section=section, content=getattr(revision, f"previous_{field}"))


def _migrate_odontogram(ctx, apps):
    OdontogramTooth = apps.get_model("consulta_medica", "OdontogramTooth")
    Odontogram = apps.get_model("consulta_medica", "Odontogram")
    OdontogramToothState = apps.get_model("consulta_medica", "OdontogramToothState")
    states = {state.code: state for state in ctx.CatEstadoPieza.objects.all()}

    patients = (
        OdontogramTooth.objects.filter(is_active=True)
        .values("no_exp", "pk_num")
        .annotate(last_update=Max("updated_at"))
    )
    for patient in patients:
        teeth = list(OdontogramTooth.objects.filter(
            no_exp=patient["no_exp"], pk_num=patient["pk_num"], is_active=True,
        ).order_by("updated_at"))
        last_user = teeth[-1].updated_by_id if teeth else None
        deciduous = any(tooth.tooth_fdi[0] in "5678" for tooth in teeth)
        permanent = any(tooth.tooth_fdi[0] in "1234" for tooth in teeth)
        dentition = "M" if deciduous and permanent else ("T" if deciduous else "P")

        counts = {"C": 0, "P": 0, "O": 0}
        for tooth in teeth:
            component = states[tooth.condition].dmft_component if tooth.condition in states else None
            if component:
                counts[component] += 1

        odontogram = Odontogram.objects.create(
            no_exp=patient["no_exp"], pk_num=patient["pk_num"], dentition=dentition,
            dmft_decayed=counts["C"], dmft_missing=counts["P"], dmft_filled=counts["O"],
            origin="migrated", created_by_id=last_user,
        )
        if patient["last_update"]:
            Odontogram.objects.filter(pk=odontogram.pk).update(created_at=patient["last_update"])
        for tooth in teeth:
            OdontogramToothState.objects.create(
                odontogram=odontogram, tooth_id=tooth.tooth_fdi, face="",
                state=states.get(tooth.condition) or states["healthy"],
                observation=tooth.notes,
            )


def forwards(apps, schema_editor):
    ctx = _Ctx(apps)
    _migrate_clinical_history(ctx, apps)
    _migrate_stomatology_history(ctx, apps)
    _migrate_revisions(ctx, apps)
    _migrate_odontogram(ctx, apps)
    ctx.Allergy.objects.filter(is_active=False).update(status="entered_in_error")


class Migration(migrations.Migration):
    dependencies = [
        ("consulta_medica", "0028_historia_clinica_unificada_esquema"),
        ("catalogos", "0032_seed_catalogos_historia_clinica"),
    ]

    operations = [
        # Sin reversa: 0030 borra las columnas de origen, y revertir exigiria
        # reconstruir texto acumulado a partir de filas -- no tiene sentido.
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
