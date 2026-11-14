# Origen del diagnostico de la inscripcion (docs/plans/cronicos-alta-padron.md).
# Solo esquema: dos columnas que admiten vacio; no escribe datos.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padrones', '0005_control_cronico'),
        ('recepcion', '0039_cita_reprogramada_de'),
    ]

    operations = [
        migrations.AddField(
            model_name='chronicenrollment',
            name='source',
            field=models.CharField(blank=True, choices=[('consulta', 'Consulta médica'), ('manual', 'Captura en Padrones')], db_column='origen', max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='chronicenrollment',
            name='visit',
            field=models.ForeignKey(blank=True, db_column='id_visit', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='recepcion.visit'),
        ),
    ]
