from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Solo estado: CatEmpleado es managed=False, Django no ejecuta SQL.
    Las columnas se crean con storage/expedientes-ddl/003_curp_sexo_cat_empleados.sql.
    """

    dependencies = [
        ('administracion', '0010_bitacora_acceso'),
    ]

    operations = [
        migrations.AddField(
            model_name='catempleado',
            name='curp',
            field=models.CharField(blank=True, db_column='curp', max_length=18, null=True),
        ),
        migrations.AddField(
            model_name='catempleado',
            name='cd_sexo',
            field=models.CharField(blank=True, db_column='cd_sexo', max_length=1, null=True),
        ),
    ]
