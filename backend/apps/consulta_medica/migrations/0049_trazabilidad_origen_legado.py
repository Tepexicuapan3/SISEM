"""
5.2 paso 5: trazabilidad del legado.

- cns_allergy.texto_original: el texto tal como venia en la historia.
- cns_clinical_history.tabla_origen / no_hisclin_origen: de que fila salio.

Relleno de lo ya migrado, solo con evidencia en los datos (nunca se adivina):
- Origen de la historia: el ref_origen de sus notas historicas y signos del
  legado ("his_clinica:123", "his_clinicad:45:..."). Gana his_clinica, igual
  que en el importador.
- Texto original de la alergia: solo las de medicina general sin usuario (las
  importo el comando) cuya nota historica "alergias" del mismo paciente
  contiene la sustancia. Las demas quedan NULL: el texto sigue en la nota.
"""
import re

from django.db import migrations, models

_REF = re.compile(r"^(his_clinicad?):(\d+)")


def backfill_history_origin(apps, schema_editor):
    ClinicalHistory = apps.get_model("consulta_medica", "ClinicalHistory")
    HistoricalNote = apps.get_model("consulta_medica", "HistoricalNote")
    LegacyVitalSigns = apps.get_model("consulta_medica", "LegacyVitalSigns")

    candidates = {}
    for model in (HistoricalNote, LegacyVitalSigns):
        rows = model.objects.filter(legacy_ref__startswith="his_clinica").values_list(
            "clinical_history_id", "legacy_ref",
        )
        for history_id, ref in rows:
            match = _REF.match(ref or "")
            if match:
                candidates.setdefault(history_id, set()).add((match.group(1), int(match.group(2))))

    pending = ClinicalHistory.objects.filter(legacy_source_table__isnull=True, pk__in=candidates.keys())
    for history_id in pending.values_list("pk", flat=True):
        found = candidates[history_id]
        general = sorted(number for table, number in found if table == "his_clinica")
        table, number = ("his_clinica", general[0]) if general else (
            "his_clinicad", min(number for _table, number in found)
        )
        ClinicalHistory.objects.filter(pk=history_id).update(legacy_source_table=table, legacy_source_id=number)


def backfill_allergy_original_text(apps, schema_editor):
    Allergy = apps.get_model("consulta_medica", "Allergy")
    HistoricalNote = apps.get_model("consulta_medica", "HistoricalNote")

    imported = Allergy.objects.filter(
        original_text__isnull=True, created_by_id__isnull=True, service_origin_code=1,
    ).only("pk", "no_exp", "pk_num", "substance")
    for allergy in imported:
        notes = HistoricalNote.objects.filter(
            no_exp=allergy.no_exp, pk_num=allergy.pk_num, section="alergias",
            content__icontains=allergy.substance,
        ).values_list("content", flat=True)
        content = next(iter(notes), None)
        if content:
            Allergy.objects.filter(pk=allergy.pk).update(original_text=content)


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0048_habito_historial"),
    ]

    operations = [
        migrations.AddField(
            model_name="allergy",
            name="original_text",
            field=models.TextField(blank=True, db_column="texto_original", null=True),
        ),
        migrations.AddField(
            model_name="clinicalhistory",
            name="legacy_source_id",
            field=models.IntegerField(blank=True, db_column="no_hisclin_origen", null=True),
        ),
        migrations.AddField(
            model_name="clinicalhistory",
            name="legacy_source_table",
            field=models.CharField(blank=True, db_column="tabla_origen", max_length=20, null=True),
        ),
        migrations.RunPython(backfill_history_origin, migrations.RunPython.noop),
        migrations.RunPython(backfill_allergy_original_text, migrations.RunPython.noop),
    ]
