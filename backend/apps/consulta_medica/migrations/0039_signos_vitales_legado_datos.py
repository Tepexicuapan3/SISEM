"""
Convierte las notas historicas "signos_vitales" que ya hubiera creado el
importador legacy (texto "Ultima medicion registrada (fecha desconocida):
Peso: 70; Talla: 1.65; ...") en filas numericas de cns_signos_vitales_legado,
y borra la nota. Reversible: el reverse recrea la nota desde `raw_text`.
Idempotente por `legacy_ref`.
"""
from django.db import migrations

from apps.consulta_medica.services.legacy_history_parsing import parse_legacy_vitals

NOTE_PREFIX = "Ultima medicion registrada (fecha desconocida): "
LABEL_TO_ARG = {
    "Peso": "weight",
    "Talla": "height",
    "TA": "blood_pressure",
    "Pulso": "pulse",
    "Temperatura": "temperature",
    "Respiracion": "respiration",
}


def _raw_values(text):
    values = {}
    for part in text.split("; "):
        label, _, value = part.partition(": ")
        if label in LABEL_TO_ARG:
            values[LABEL_TO_ARG[label]] = value
    return values


def notes_to_vitals(apps, schema_editor):
    HistoricalNote = apps.get_model("consulta_medica", "HistoricalNote")
    LegacyVitalSigns = apps.get_model("consulta_medica", "LegacyVitalSigns")
    notes = HistoricalNote.objects.filter(
        section="signos_vitales", origin="M", content__startswith=NOTE_PREFIX, legacy_ref__isnull=False,
    )
    for note in notes.iterator():
        raw_text = note.content[len(NOTE_PREFIX):]
        if not LegacyVitalSigns.objects.filter(legacy_ref=note.legacy_ref).exists():
            LegacyVitalSigns.objects.create(
                clinical_history_id=note.clinical_history_id, no_exp=note.no_exp, pk_num=note.pk_num,
                specialty=note.specialty, raw_text=raw_text, legacy_ref=note.legacy_ref,
                **parse_legacy_vitals(**_raw_values(raw_text)),
            )
        note.delete()


def vitals_to_notes(apps, schema_editor):
    HistoricalNote = apps.get_model("consulta_medica", "HistoricalNote")
    LegacyVitalSigns = apps.get_model("consulta_medica", "LegacyVitalSigns")
    for vitals in LegacyVitalSigns.objects.iterator():
        HistoricalNote.objects.create(
            clinical_history_id=vitals.clinical_history_id, no_exp=vitals.no_exp, pk_num=vitals.pk_num,
            specialty=vitals.specialty, section="signos_vitales", origin="M",
            content=f"{NOTE_PREFIX}{vitals.raw_text}", legacy_ref=vitals.legacy_ref,
        )
    LegacyVitalSigns.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0038_signos_vitales_legado"),
    ]

    operations = [
        migrations.RunPython(notes_to_vitals, vitals_to_notes),
    ]
