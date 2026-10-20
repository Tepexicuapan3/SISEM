# Paso 2 de `medicos-legado-archivo`: se retira el import masivo de médicos
# por Excel (ya no se crean médicos sin usuario). El historial de jobs era
# solo de TEST y no tiene valor clínico.
#
# Rollback: `migrate medicos 0015` (recrea la tabla vacía).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('medicos', '0015_legacy_medico_medico_externo'),
    ]

    operations = [
        migrations.DeleteModel(
            name='MedicoImportJob',
        ),
    ]
