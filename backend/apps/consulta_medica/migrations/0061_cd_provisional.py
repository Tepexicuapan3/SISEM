"""
Plan identidad del paciente: el recien nacido provisional deja de usar
cd_familiar (que queda solo para el legado) y pasa a su propia columna
cd_provisional. Esta migracion solo expande (columna, unico y CHECK con la
tercera llave); 0062 mueve los datos. Van aparte porque en Postgres llenar
filas y alterar restricciones en la misma transaccion falla con "pending
trigger events" (mismo motivo que 0057/0058).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0060_legado_db_origen"),
    ]

    operations = [
        migrations.AddField(
            model_name="patient",
            name="provisional_code",
            field=models.IntegerField(blank=True, db_column="cd_provisional", null=True),
        ),
        migrations.AddConstraint(
            model_name="patient",
            constraint=models.UniqueConstraint(
                condition=models.Q(provisional_code__isnull=False),
                fields=("provisional_code",), name="cns_paciente_cd_provisional_uq",
            ),
        ),
        migrations.RemoveConstraint(model_name="patient", name="cns_paciente_con_identificador"),
        migrations.AddConstraint(
            model_name="patient",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(pk_num__isnull=False)
                    | models.Q(legacy_family_code__isnull=False)
                    | models.Q(provisional_code__isnull=False)
                ),
                name="cns_paciente_con_identificador",
            ),
        ),
    ]
