# Fix forward-only para bases donde `medicos.0007_switch_surrogate_pk` YA
# está aplicada SIN el fix de esta sesión (ver cabecera de 0007 y Engram,
# sdd/medico-pk-independiente/design, sección 10.5).
#
# `0007` declara `nombre_display` en `state_operations` (Django ya lo
# conoce desde ahí) pero nunca emitía el `ALTER TABLE ... ADD COLUMN`
# correspondiente en `database_operations` -- gap real, no gap de estado.
# Por eso esta migración es SOLO `RunSQL`, sin `state_operations` ni
# `SeparateDatabaseAndState`: `RunSQL` no toca el estado de Django (no
# implementa un `state_forwards` propio, a diferencia de `AddField`), así
# que no hay riesgo de que Django intente un `AddField` duplicado sobre un
# campo que el estado ya tiene desde `0007`. `makemigrations --check
# --dry-run` se verificó limpio con este archivo en el árbol (ver reporte).
#
# `IF NOT EXISTS`/`IF EXISTS` para que sea segura de re-correr incluso si
# la columna ya existiera parcialmente (p.ej. alguien la agregó a mano).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("medicos", "0008_alter_catmedico_id"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE cat_medicos ADD COLUMN IF NOT EXISTS nombre_display varchar(200) NULL;",
            reverse_sql="ALTER TABLE cat_medicos DROP COLUMN IF EXISTS nombre_display;",
        ),
    ]
