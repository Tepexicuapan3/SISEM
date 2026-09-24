# Esquema puro, SIN backfill (ver Engram, topic_key
# sdd/medicos-legacy-field-bulk-import/design, "Decisión 5").
#
# `AddField` estándar: no hace falta backfill porque deja NULL en toda fila
# existente, y `unique=True` sobre N filas con `legacy_cd_medico=NULL` no
# dispara conflicto ni en Postgres ni en SQLite (ambos motores tratan
# múltiples NULL como valores distintos, no iguales entre sí). Los médicos
# nativos de SIRES (sin origen legado) quedan correctamente en NULL.
#
# NO replica el patrón `RunPython`+introspección de `0009_add_nombre_
# display_column`: aquella migración corrigió un drift puntual (columna ya
# declarada en el `state_operations` de `0007_switch_surrogate_pk` sin el
# `ALTER TABLE` correspondiente). `legacy_cd_medico` es un campo nuevo sin
# drift posible -- `AddField` normal es correcto y suficiente aquí.
#
# Rollback: `migrate medicos 0009` (columna aditiva, nullable, sin
# dependientes ni datos que perder).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medicos', '0009_add_nombre_display_column'),
    ]

    operations = [
        migrations.AddField(
            model_name='catmedico',
            name='legacy_cd_medico',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
    ]
