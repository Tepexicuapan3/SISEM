# FASE 2 (EXPAND) del cambio `medico-pk-independiente` -- ver Engram,
# topic_key sdd/medico-pk-independiente/design, secciones 0 y 2.
#
# F1-03 (congelamiento, red de seguridad Fase 1): a partir de esta migración
# y durante TODO el cambio `medico-pk-independiente` (0004..0008), ningún
# `related_name` ni `db_column` existente se renombra. Un rename simultáneo
# al cambio de PK vuelve el diff imposible de auditar -- ver propuesta
# (obs #467, Fase 0). Si algo necesita renombrarse, es un cambio SDD aparte,
# posterior a este.
#
# Decisión D4 del diseño: Django 6 no puede representar el estado
# intermedio -- un modelo admite una sola PK y `fields.E100` prohíbe un
# `BigAutoField` que no sea PK, así que es imposible declarar `id` en el
# modelo mientras `id_usuario` siga siendo la PK. Por eso `state_operations`
# queda vacío: el modelo Python NO cambia una sola línea en esta migración,
# todo es SQL contra la base de datos únicamente (SeparateDatabaseAndState).
#
# Esta migración es puramente ADITIVA: agrega `cat_medicos.id` (poblada para
# las filas existentes) y 9 columnas espejo `*_legacy` (NULL, sin backfillear
# todavía -- eso es la Fase 3/0006). La app vieja sigue funcionando intacta:
# nadie lee las columnas nuevas. Cero downtime, cero riesgo funcional.
#
# Portabilidad (hallazgo NO contemplado en el diseño original): este
# proyecto corre `manage.py test` contra SQLite en memoria
# (`config/settings.py`, `if "test" in sys.argv`), NO contra Postgres --
# ver precedente ya establecido en `catalogos/0015_reconcile_catcentroatencion_drift.py`
# y `somatometria/0005_latest_vitals_pknum_rebuild.py`, que documentan y
# resuelven el mismo problema. `bigserial` y `CONCURRENTLY` no existen en
# SQLite, así que esta migración rama por `connection.vendor`: Postgres usa
# exactamente el SQL del diseño; SQLite usa un equivalente funcional
# (columna `bigint` + backfill secuencial en Python + índice único sin
# `CONCURRENTLY`) que alcanza el mismo estado final para que los tests del
# proyecto (que SÍ corren esta migración al construir la base de datos de
# prueba) sigan funcionando.
from django.db import migrations

# Las 9 columnas espejo `*_legacy` (8 modelos, `rel_medico_cobertura` aporta
# dos) -- copia exacta del valor viejo (id de usuario) para que el rollback
# de Fase 4 sea un UPDATE, no un recálculo. Ver design, Decisión D1.
LEGACY_MIRROR_COLUMNS = [
    ("rel_medico_especialidad", "medico_id_legacy"),
    ("rel_medico_centro", "medico_id_legacy"),
    ("rel_medico_consultorio", "medico_id_legacy"),
    ("rel_medico_excepcion", "medico_id_legacy"),
    ("rel_medico_cobertura", "medico_suplente_id_legacy"),
    ("rel_medico_cobertura", "medico_titular_id_legacy"),
    ("citas_medicas", "medico_id_legacy"),
    ("citas_horarios_disponibles", "medico_id_legacy"),
    ("almacen_consumos_consulta", "medico_id_legacy"),
]


def _add_id_column_postgres(cursor):
    # bigserial es exactamente el tipo que Django mapea a BigAutoField en
    # Postgres, y la secuencia se autonombra `cat_medicos_id_seq` -- el
    # nombre que el ORM va a esperar en Fase 4. Reescribe la tabla (ACCESS
    # EXCLUSIVE); en cat_medicos (volumen bajo) es de segundos.
    cursor.execute("ALTER TABLE cat_medicos ADD COLUMN id bigserial;")
    cursor.execute("ALTER TABLE cat_medicos ADD CONSTRAINT cat_medicos_id_key UNIQUE (id);")


def _add_id_column_sqlite(cursor):
    cursor.execute("ALTER TABLE cat_medicos ADD COLUMN id bigint;")
    cursor.execute("SELECT id_usuario FROM cat_medicos ORDER BY rowid")
    rows = cursor.fetchall()
    for seq, (id_usuario,) in enumerate(rows, start=1):
        cursor.execute("UPDATE cat_medicos SET id = %s WHERE id_usuario = %s", [seq, id_usuario])
    cursor.execute("CREATE UNIQUE INDEX cat_medicos_id_key ON cat_medicos (id);")


def expand_forwards(apps, schema_editor):
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    with connection.cursor() as cursor:
        if is_postgres:
            _add_id_column_postgres(cursor)
        else:
            _add_id_column_sqlite(cursor)

        for table, column in LEGACY_MIRROR_COLUMNS:
            cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" bigint;')


def expand_backwards(apps, schema_editor):
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    with connection.cursor() as cursor:
        for table, column in LEGACY_MIRROR_COLUMNS:
            cursor.execute(f'ALTER TABLE "{table}" DROP COLUMN "{column}";')

        if is_postgres:
            cursor.execute("ALTER TABLE cat_medicos DROP CONSTRAINT cat_medicos_id_key;")
        else:
            cursor.execute("DROP INDEX IF EXISTS cat_medicos_id_key;")
        cursor.execute("ALTER TABLE cat_medicos DROP COLUMN id;")


class Migration(migrations.Migration):

    dependencies = [
        ("medicos", "0003_relmedicoconsultoriohorario_canal"),
        # Gap 10.3 (design, topic sdd/medico-pk-independiente/design): las
        # operaciones de esta migración tocan columnas de `citas_medicas` /
        # `citas_horarios_disponibles` (recepcion) y `almacen_consumos_consulta`
        # (almacen_insumos) -- sin estas dependencias, `migrate` desde una DB
        # vacía puede aplicar esta migración antes de que esas tablas existan
        # (`OperationalError: no such table: citas_medicas`), rompiendo la
        # suite de tests completa y el gate de CI de D3. Se ancla a la última
        # migración real de cada app (confirmado leyendo el directorio de
        # migraciones, no inventado): `recepcion` no tiene ninguna migración
        # posterior a la 0024 que dependa de ella, e igual para
        # `almacen_insumos` 0002. Sin ciclo: ninguna migración de recepcion
        # depende de medicos más allá de 0002, y almacen_insumos/0002 ya
        # depende de medicos/0003 (anterior a esta).
        ("recepcion", "0024_motivo_cancelacion_catalogo"),
        ("almacen_insumos", "0002_medico_fk_integrity"),
    ]

    # F2-01 en tasks (obs #473): bloqueado por F1-02 (D3, gate de CI que
    # corre `migrate` desde DB vacía) -- ese job ya se agregó en
    # .github/workflows/ci.yml (job `backend-migrate-empty-db`) en esta
    # misma sesión, así que esta migración puede avanzar.
    atomic = True

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunPython(expand_forwards, expand_backwards),
            ],
        ),
    ]
