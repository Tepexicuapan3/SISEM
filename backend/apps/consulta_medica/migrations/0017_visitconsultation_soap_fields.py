from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0016_visitprescriptionitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="visitconsultation",
            name="subjective",
            field=models.TextField(blank=True, db_column="subjetivo", null=True),
        ),
        migrations.AddField(
            model_name="visitconsultation",
            name="objective",
            field=models.TextField(blank=True, db_column="objetivo", null=True),
        ),
        migrations.AddField(
            model_name="visitconsultation",
            name="assessment",
            field=models.TextField(blank=True, db_column="analisis", null=True),
        ),
        migrations.AddField(
            model_name="visitconsultation",
            name="plan",
            field=models.TextField(blank=True, db_column="plan", null=True),
        ),
        migrations.AddField(
            model_name="visitconsultationrevision",
            name="previous_subjective",
            field=models.TextField(blank=True, db_column="subjetivo_anterior", null=True),
        ),
        migrations.AddField(
            model_name="visitconsultationrevision",
            name="previous_objective",
            field=models.TextField(blank=True, db_column="objetivo_anterior", null=True),
        ),
        migrations.AddField(
            model_name="visitconsultationrevision",
            name="previous_assessment",
            field=models.TextField(blank=True, db_column="analisis_anterior", null=True),
        ),
        migrations.AddField(
            model_name="visitconsultationrevision",
            name="previous_plan",
            field=models.TextField(blank=True, db_column="plan_anterior", null=True),
        ),
    ]
