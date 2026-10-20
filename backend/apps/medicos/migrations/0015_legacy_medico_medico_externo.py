# Paso 1 (expandir, aditivo) de `medicos-legado-archivo`.
#
# - `legacy_medico`: archivo de SOLO LECTURA de `cat_medicos` del SISEM legado.
#   Se carga a mano por SQL (INSERT ... SELECT); las columnas espejan los
#   nombres del legado.
# - `medico_externo`: profesionales de salud externos (solo la tabla).
#
# Rollback: `migrate medicos 0014`.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medicos', '0014_catmedico_sexo_fecha_nac'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegacyMedico',
            fields=[
                ('no_medico', models.IntegerField(primary_key=True, serialize=False)),
                ('cd_medico', models.CharField(max_length=10)),
                ('ds_paterno', models.CharField(blank=True, max_length=45, null=True)),
                ('ds_materno', models.CharField(blank=True, max_length=45, null=True)),
                ('ds_nombre', models.CharField(blank=True, max_length=45, null=True)),
                ('cd_sexo', models.CharField(blank=True, max_length=1, null=True)),
                ('fe_nac', models.DateField(blank=True, null=True)),
                ('no_cedula', models.CharField(blank=True, max_length=20, null=True)),
                ('cd_clinica', models.IntegerField(blank=True, null=True)),
                ('ds_clinica', models.CharField(blank=True, max_length=150, null=True)),
                ('cd_especialidad', models.IntegerField(blank=True, null=True)),
                ('ds_especialidad', models.CharField(blank=True, max_length=150, null=True)),
                ('sw_status', models.CharField(max_length=1)),
                ('cd_usuario', models.CharField(blank=True, max_length=10, null=True)),
                ('fch_carga', models.DateTimeField(auto_now_add=True)),
                ('medico_actual', models.ForeignKey(blank=True, db_column='id_medico_actual', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registros_legado', to='medicos.catmedico')),
            ],
            options={
                'verbose_name': 'Médico legado',
                'verbose_name_plural': 'Médicos legado',
                'db_table': 'legacy_medico',
                'indexes': [
                    models.Index(fields=['cd_medico'], name='legacy_medico_cd_medico_idx'),
                    models.Index(fields=['no_cedula'], name='legacy_medico_no_cedula_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='MedicoExterno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origen', models.CharField(max_length=20)),
                ('id_externo', models.CharField(max_length=50)),
                ('nombre', models.CharField(max_length=80)),
                ('paterno', models.CharField(blank=True, max_length=80, null=True)),
                ('materno', models.CharField(blank=True, max_length=80, null=True)),
                ('cedula_profesional', models.CharField(blank=True, db_index=True, max_length=30, null=True)),
                ('institucion', models.CharField(blank=True, max_length=150, null=True)),
                ('especialidad_texto', models.CharField(blank=True, max_length=150, null=True)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Médico externo',
                'verbose_name_plural': 'Médicos externos',
                'db_table': 'medico_externo',
                'constraints': [
                    models.UniqueConstraint(fields=('origen', 'id_externo'), name='medico_externo_origen_id_externo_uniq'),
                ],
            },
        ),
    ]
