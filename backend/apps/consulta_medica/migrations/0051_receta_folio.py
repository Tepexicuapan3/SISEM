"""
5.3: folio de receta "RX-<anio>-<consecutivo>" (cabecera RECETA del documento).

Las recetas que ya existen reciben su folio por orden de creacion, con el
consecutivo de su anio, y el contador de cada anio queda en el ultimo numero
usado: la siguiente receta continua la serie sin repetir. Solo se leen las
columnas escalares (pk, fecha): `items` es jsonb y no se toca.
"""
from django.db import migrations, models
from django.utils import timezone


def backfill_folios(apps, schema_editor):
    VisitPrescription = apps.get_model("consulta_medica", "VisitPrescription")
    Counter = apps.get_model("consulta_medica", "PrescriptionFolioCounter")

    last_by_year = {}
    rows = (
        VisitPrescription.objects.filter(folio__isnull=True)
        .order_by("created_at", "pk")
        .values_list("pk", "created_at")
    )
    for pk, created_at in rows:
        moment = created_at or timezone.now()
        year = timezone.localtime(moment).year if timezone.is_aware(moment) else moment.year
        sequence = last_by_year.get(year, 0) + 1
        last_by_year[year] = sequence
        VisitPrescription.objects.filter(pk=pk).update(
            folio=f"RX-{year}-{sequence:06d}", sequence=sequence,
        )
    for year, last_value in last_by_year.items():
        Counter.objects.update_or_create(year=year, defaults={"last_value": last_value})


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0050_nota_morbilidad_seguimiento"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrescriptionFolioCounter",
            fields=[
                ("year", models.PositiveSmallIntegerField(db_column="anio", primary_key=True, serialize=False)),
                ("last_value", models.PositiveIntegerField(db_column="ultimo", default=0)),
            ],
            options={
                "db_table": "cns_consecutivo_receta",
            },
        ),
        migrations.AddField(
            model_name="visitprescription",
            name="folio",
            field=models.CharField(blank=True, db_column="no_freceta", max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="visitprescription",
            name="prescription_type",
            field=models.CharField(
                choices=[("N", "Normal"), ("T", "Transcripcion")], db_column="tp_receta", default="N", max_length=1,
            ),
        ),
        migrations.AddField(
            model_name="visitprescription",
            name="sequence",
            field=models.PositiveIntegerField(blank=True, db_column="no_receta", null=True),
        ),
        migrations.RunPython(backfill_folios, migrations.RunPython.noop),
    ]
