from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0002_alter_detusuarioadministrativo_options_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DetUsuarioAdministrativo',
        ),
        migrations.DeleteModel(
            name='DetUsuarioEnfermeria',
        ),
        migrations.DeleteModel(
            name='DetUsuarioMedico',
        ),
    ]
