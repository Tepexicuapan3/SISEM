# Paso 4 (contraer) de `medicos-legado-archivo`.
#
# Todo médico tiene usuario: se eliminan los datos personales propios de
# `cat_medicos` (la identidad vive en DetUsuario / DetUsuarioCedula) y
# `id_usuario` pasa a OneToOne NOT NULL con PROTECT.
#
# ANTES de aplicarla (TEST):
#     SELECT count(*) FROM cat_medicos WHERE id_usuario IS NULL;   -- debe ser 0
# El precheck de abajo aborta con un error claro si no lo es.
#
# Rollback: `migrate medicos 0016` recrea las columnas VACÍAS (los datos
# personales descartados no se recuperan).

import django.db.models.deletion
from django.db import migrations, models


def _precheck_sin_usuario(apps, schema_editor):
    CatMedico = apps.get_model("medicos", "CatMedico")
    db = schema_editor.connection.alias
    n = CatMedico.objects.using(db).filter(id_usuario__isnull=True).count()
    if n:
        raise RuntimeError(
            f"Hay {n} médicos sin usuario; vaciar/asignar antes de migrar "
            "(SELECT count(*) FROM cat_medicos WHERE id_usuario IS NULL debe ser 0)."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0016_alter_detusuario_sexo'),
        ('medicos', '0016_delete_medicoimportjob'),
    ]

    operations = [
        migrations.RunPython(_precheck_sin_usuario, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='catmedico',
            name='cat_medicos_datos_personales_solo_sin_usuario',
        ),
        migrations.RemoveField(model_name='catmedico', name='nombre'),
        migrations.RemoveField(model_name='catmedico', name='paterno'),
        migrations.RemoveField(model_name='catmedico', name='materno'),
        migrations.RemoveField(model_name='catmedico', name='cedula_profesional'),
        migrations.RemoveField(model_name='catmedico', name='id_escuela'),
        migrations.RemoveField(model_name='catmedico', name='sexo'),
        migrations.RemoveField(model_name='catmedico', name='fecha_nac'),
        migrations.AlterField(
            model_name='catmedico',
            name='id_usuario',
            field=models.OneToOneField(db_column='id_usuario', on_delete=django.db.models.deletion.PROTECT, related_name='medico', to='authentication.syusuario'),
        ),
    ]
