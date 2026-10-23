"""
Plan identidad del paciente, Fase 3 (contraer): id_persona obligatorio. Desde
aqui Patient.save() crea la persona de cada registro nuevo.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0057_persona"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="person",
            field=models.ForeignKey(
                db_column="id_persona", on_delete=django.db.models.deletion.PROTECT,
                related_name="records", to="consulta_medica.person",
            ),
        ),
    ]
