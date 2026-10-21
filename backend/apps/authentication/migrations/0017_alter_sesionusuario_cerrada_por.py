from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0016_alter_detusuario_sexo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sesionusuario',
            name='cerrada_por',
            field=models.CharField(blank=True, choices=[('LOGOUT', 'Logout'), ('EXPIRACION', 'Expiración'), ('REVOCADA', 'Revocada')], max_length=10, null=True),
        ),
    ]
