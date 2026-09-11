# FASE 4 (SWITCH) del cambio `medico-pk-independiente` -- la única fase con
# ventana de riesgo real. Ver Engram, sdd/medico-pk-independiente/design,
# sección 4. Código de aplicación (identity.py, usecases, views) se actualiza
# en el MISMO commit -- ver `backend/apps/medicos/identity.py` y los fixes en
# `apps/recepcion/uses_case/*`, `apps/medicos/views/medico_views.py`, etc.
#
# CORRECCIÓN respecto del diseño original (hallazgo verificado leyendo
# `django/db/backends/base/schema.py::sql_create_fk` en esta sesión, NO
# contemplado en obs #469): Django JAMÁS emite `ON DELETE ...` en el DDL de
# una FK -- ni para CASCADE, ni para SET_NULL, ni para PROTECT. `on_delete`
# se resuelve ENTERAMENTE en Python (`django.db.models.deletion.Collector`)
# cuando el borrado pasa por el ORM (`.delete()`). El diseño asumía que
# había que recrear las 9 FKs con `ON DELETE CASCADE`/`ON DELETE SET NULL`
# explícito en la base de datos -- eso NO es lo que Django genera en
# ninguna otra migración de este proyecto (se verificó también que
# `django/db/backends/postgresql/schema.py` no tiene ninguna lógica de
# `on_delete` propia). Recrear las FKs con esas cláusulas habría dejado el
# esquema físicamente INCONSISTENTE con el resto de la base (cascadas reales
# a nivel DB que no existen en ningún otro lado) y further, la FK de
# `id_usuario -> sy_usuarios` NO se toca en absoluto en este switch: su
# `on_delete` pasa de CASCADE a SET_NULL únicamente en el modelo Python
# (F4-10, models.py) -- el ORM ya lo resuelve solo al borrar vía `.delete()`,
# igual que hoy. Las 9 FKs nuevas se recrean como FKs planas (sin `ON
# DELETE`), igual que las que reemplazan.
#
# Gap real corregido en esta sesión (ver Engram, sdd/medico-pk-independiente
# /design, sección 10.5): el `AddField` de `nombre_display` en
# `state_operations` (más abajo) nunca tuvo su DDL correspondiente en
# `database_operations` -- ni en Postgres ni en SQLite. La columna física
# nunca se creaba, así que cualquier consulta que tocara
# `cat_medicos.nombre_display` (p.ej. `GET /api/v1/medicos`) reventaba con
# `ProgrammingError: no existe la columna cat_medicos.nombre_display`. Fix:
# `ALTER TABLE cat_medicos ADD COLUMN nombre_display varchar(200) NULL;` en
# `_switch_forwards_postgres` (con su reversa simétrica en
# `_switch_backwards_postgres`) y una rama equivalente en
# `_sqlite_rebuild_cat_medicos`. Aditivo, sin riesgo de bloqueo ni de
# pérdida de datos. Para bases que YA tenían 0007 aplicada antes de este
# fix (este cambio al archivo no se re-ejecuta solo), ver
# `medicos/0009_add_nombre_display_column.py`.
#
# Portabilidad (mismo hallazgo que 0004/0005/0006 -- `manage.py test` corre
# contra SQLite en memoria): el switch de PK con descubrimiento de
# constraints vía `pg_constraint`, `NOT VALID`/`VALIDATE CONSTRAINT` y
# `SET LOCAL lock_timeout` es intrínsecamente específico de Postgres. Para
# SQLite (solo se ejecuta bajo el test runner del proyecto) se usa la
# técnica de reconstrucción de tabla ya usada en este repo
# (`catalogos/0015_reconcile_catcentroatencion_drift.py`,
# `_sqlite_drop_not_null`) extendida a las tablas dependientes, con
# `PRAGMA foreign_keys=OFF` durante la reconstrucción (se reactiva al final,
# con las 9 columnas ya apuntando al lugar correcto).
import re

from django.db import migrations, models
import django.db.models.deletion

# (tabla, columna_medico, columna_legacy, columna_pk) -- mismo inventario
# que 0006_backfill_legacy_ids.py.
FK_COLUMNS = [
    ("rel_medico_especialidad", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_centro", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_consultorio", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_excepcion", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_cobertura", "medico_suplente_id", "medico_suplente_id_legacy", "id"),
    ("rel_medico_cobertura", "medico_titular_id", "medico_titular_id_legacy", "id"),
    ("citas_medicas", "medico_id", "medico_id_legacy", "id"),
    ("citas_horarios_disponibles", "medico_id", "medico_id_legacy", "id"),
    ("almacen_consumos_consulta", "medico_id", "medico_id_legacy", "id_consumo"),
]


# ─── Postgres ─────────────────────────────────────────────────────────────

def _discover_fk_names(cursor, table, column, ref_table):
    cursor.execute(
        """
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel  ON rel.oid  = con.conrelid
        JOIN pg_class frel ON frel.oid = con.confrelid
        JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
        WHERE con.contype = 'f' AND rel.relname = %s AND att.attname = %s AND frel.relname = %s
          -- Acotar al schema activo (current_schema() == primer hit de
          -- search_path): sin esto, un schema viejo homónimo (p.ej. "public"
          -- con tablas fantasma de antes de adoptar el schema "sires") hace
          -- que esta query devuelva mas de 1 constraint para la MISMA tabla
          -- logica -- ver post-mortem 2026-09-10, almacen_consumos_consulta.
          AND rel.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = current_schema())
        """,
        [table, column, ref_table],
    )
    return [row[0] for row in cursor.fetchall()]


def _discover_pk_name(cursor, table):
    cursor.execute(
        "SELECT conname FROM pg_constraint WHERE contype = 'p' AND conrelid = %s::regclass",
        [table],
    )
    return [row[0] for row in cursor.fetchall()]


def _switch_forwards_postgres(cursor):
    cursor.execute("SET LOCAL lock_timeout = '5s';")

    # Línea base (F4-06) -- se compara al final, cualquier diferencia aborta
    # (y con ella, revierte toda la transacción: DDL en Postgres es
    # transaccional).
    baseline = {}
    for table, medico_col, _legacy_col, _pk_col in FK_COLUMNS:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{medico_col}" IS NOT NULL')
        baseline[(table, medico_col)] = cursor.fetchone()[0]

    # F4-02 (D5) -- descubrir los nombres de constraint, nunca hardcodear.
    fk_names = {}
    for table, medico_col, _legacy_col, _pk_col in FK_COLUMNS:
        names = _discover_fk_names(cursor, table, medico_col, "cat_medicos")
        if len(names) != 1:
            raise RuntimeError(
                f"0007_switch_surrogate_pk: se esperaba exactamente 1 FK "
                f"{table}.{medico_col} -> cat_medicos, se encontraron {len(names)}: {names}"
            )
        fk_names[(table, medico_col)] = names[0]

    # F4-03 -- dropear las 9 FK entrantes ANTES de tocar la PK (Postgres
    # rechaza DROP CONSTRAINT sobre una PK con FKs dependientes). NUNCA
    # CASCADE: perderíamos el control de cuáles recrear.
    for (table, medico_col), name in fk_names.items():
        cursor.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}";')

    pk_names = _discover_pk_name(cursor, "cat_medicos")
    if len(pk_names) != 1:
        raise RuntimeError(f"0007_switch_surrogate_pk: PK inesperada en cat_medicos: {pk_names}")
    cursor.execute(f'ALTER TABLE cat_medicos DROP CONSTRAINT "{pk_names[0]}";')
    cursor.execute("ALTER TABLE cat_medicos ADD CONSTRAINT cat_medicos_pkey PRIMARY KEY (id);")
    cursor.execute("ALTER TABLE cat_medicos ALTER COLUMN id_usuario DROP NOT NULL;")
    # La FK id_usuario -> sy_usuarios NO se toca: Django no codifica on_delete
    # en DB (ver cabecera de este archivo), así que no hay DDL que cambiar.

    # F4-08bis -- gap real (ver cabecera del archivo, sección Engram 10.5):
    # el AddField de nombre_display en state_operations nunca tuvo su DDL
    # acá. Aditivo, sin riesgo.
    cursor.execute("ALTER TABLE cat_medicos ADD COLUMN nombre_display varchar(200) NULL;")

    # F4-04 -- traducción in-place, una UPDATE por columna.
    for table, medico_col, legacy_col, _pk_col in FK_COLUMNS:
        cursor.execute(
            f'UPDATE "{table}" t SET "{medico_col}" = m.id '
            f'FROM cat_medicos m WHERE t."{legacy_col}" = m.id_usuario;'
        )

    # F4-05 -- recrear las 9 FKs contra cat_medicos(id) en dos pasos (NOT
    # VALID + VALIDATE CONSTRAINT = SHARE UPDATE EXCLUSIVE, no bloquea
    # lecturas/escrituras en citas_medicas / citas_horarios_disponibles).
    for table, medico_col, _legacy_col, _pk_col in FK_COLUMNS:
        fk_name = f"{table}_{medico_col}_fkey_v2"
        cursor.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{fk_name}" '
            f'FOREIGN KEY ("{medico_col}") REFERENCES cat_medicos (id) NOT VALID;'
        )
        cursor.execute(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{fk_name}";')

    # F4-06 -- aserción final: los conteos por tabla deben coincidir con la
    # línea base. VALIDATE CONSTRAINT ya habría fallado si algún medico_col
    # quedó apuntando a un id inexistente; esto cubre además "se perdieron
    # filas NOT NULL" (poco probable, pero el design lo pide explícito).
    for table, medico_col, _legacy_col, _pk_col in FK_COLUMNS:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{medico_col}" IS NOT NULL')
        after = cursor.fetchone()[0]
        if after != baseline[(table, medico_col)]:
            raise RuntimeError(
                f"0007_switch_surrogate_pk: conteo de {table}.{medico_col} cambió "
                f"durante el switch ({baseline[(table, medico_col)]} -> {after})."
            )


def _switch_backwards_postgres(cursor):
    for table, medico_col, legacy_col, _pk_col in FK_COLUMNS:
        for name in _discover_fk_names(cursor, table, medico_col, "cat_medicos"):
            cursor.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}";')
        # Valores originales exactos, sin recomputar nada (D1).
        cursor.execute(f'UPDATE "{table}" SET "{medico_col}" = "{legacy_col}";')

    pk_names = _discover_pk_name(cursor, "cat_medicos")
    cursor.execute(f'ALTER TABLE cat_medicos DROP CONSTRAINT "{pk_names[0]}";')
    # Falla aquí si ya se insertó algún médico con id_usuario NULL -- por
    # diseño (D8): mientras MEDICOS_ALLOW_SIN_USUARIO esté apagado, este
    # rollback siempre es posible.
    cursor.execute("ALTER TABLE cat_medicos ADD CONSTRAINT cat_medicos_pkey PRIMARY KEY (id_usuario);")
    cursor.execute("ALTER TABLE cat_medicos ALTER COLUMN id_usuario SET NOT NULL;")
    # F4-08bis -- reversa simétrica del fix de gap (ver forwards).
    cursor.execute("ALTER TABLE cat_medicos DROP COLUMN IF EXISTS nombre_display;")

    for table, medico_col, _legacy_col, _pk_col in FK_COLUMNS:
        fk_name = f"{table}_{medico_col}_fkey_legacy"
        cursor.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{fk_name}" '
            f'FOREIGN KEY ("{medico_col}") REFERENCES cat_medicos (id_usuario);'
        )


# ─── SQLite (solo test runner) ────────────────────────────────────────────

def _sqlite_rebuild_cat_medicos(cursor, *, promote_id: bool):
    """
    promote_id=True  -> `id` pasa a PRIMARY KEY, `id_usuario` nullable+FK, y
                         se agrega `nombre_display` (F4-08bis -- mismo gap
                         real que en Postgres: la columna física nunca se
                         creaba. Ver cabecera del archivo, Engram 10.5).
    promote_id=False -> reverse: `id_usuario` vuelve a PRIMARY KEY NOT NULL,
                         y se descarta `nombre_display` (rebuild, no DROP
                         COLUMN, por compatibilidad con SQLite < 3.35).
    """
    cursor.execute('PRAGMA table_info("cat_medicos")')
    cols = cursor.fetchall()  # (cid, name, type, notnull, dflt_value, pk)
    existing_names = {name for _cid, name, *_ in cols}

    col_defs, col_names, select_exprs = [], [], []
    for _cid, name, coltype, notnull, dflt, _pk in cols:
        if name == "nombre_display" and not promote_id:
            continue  # se descarta en el rollback -- ver docstring.
        col_names.append(f'"{name}"')
        select_exprs.append(f'"{name}"')
        parts = [f'"{name}"', coltype or "bigint"]
        if name == "id":
            if promote_id:
                parts.append("PRIMARY KEY")
        elif name == "id_usuario":
            if promote_id:
                parts.append(
                    'REFERENCES "sy_usuarios" ("id_usuario") DEFERRABLE INITIALLY DEFERRED'
                )
            else:
                parts.append(
                    'NOT NULL PRIMARY KEY REFERENCES "sy_usuarios" ("id_usuario") '
                    'DEFERRABLE INITIALLY DEFERRED'
                )
        elif notnull:
            parts.append("NOT NULL")
        if dflt is not None:
            parts.append(f"DEFAULT {dflt}")
        col_defs.append(" ".join(parts))

    if promote_id and "nombre_display" not in existing_names:
        col_names.append('"nombre_display"')
        select_exprs.append("NULL")
        col_defs.append('"nombre_display" varchar(200)')

    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='cat_medicos' AND sql IS NOT NULL"
    )
    index_sqls = [row[0] for row in cursor.fetchall()]

    tmp = "cat_medicos__pk_switch_tmp"
    cursor.execute(f'CREATE TABLE "{tmp}" ({", ".join(col_defs)})')
    cols_csv = ", ".join(col_names)
    select_csv = ", ".join(select_exprs)
    cursor.execute(f'INSERT INTO "{tmp}" ({cols_csv}) SELECT {select_csv} FROM "cat_medicos"')
    cursor.execute('DROP TABLE "cat_medicos"')
    cursor.execute(f'ALTER TABLE "{tmp}" RENAME TO "cat_medicos"')
    for idx_sql in index_sqls:
        try:
            cursor.execute(idx_sql)
        except Exception:  # noqa: BLE001 -- best effort, entorno de test únicamente.
            pass


def _sqlite_repoint_fk(cursor, table, *, ref_table, old_col, new_col):
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [table])
    row = cursor.fetchone()
    if not row or not row[0]:
        return

    pattern = re.compile(
        rf'REFERENCES\s+"?{re.escape(ref_table)}"?\s*\(\s*"?{re.escape(old_col)}"?\s*\)'
    )
    new_sql, n = pattern.subn(f'REFERENCES "{ref_table}" ("{new_col}")', row[0])
    if n == 0:
        return  # best-effort: patrón no encontrado, se deja la FK física como está (solo afecta tests).

    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", [table]
    )
    index_sqls = [r[0] for r in cursor.fetchall()]

    tmp = f"{table}__fk_repoint_tmp"
    tmp_sql = re.sub(rf'\bTABLE\s+"?{re.escape(table)}"?', f'TABLE "{tmp}"', new_sql, count=1)
    cursor.execute(tmp_sql)
    cursor.execute(f'INSERT INTO "{tmp}" SELECT * FROM "{table}"')
    cursor.execute(f'DROP TABLE "{table}"')
    cursor.execute(f'ALTER TABLE "{tmp}" RENAME TO "{table}"')
    for idx_sql in index_sqls:
        try:
            cursor.execute(idx_sql)
        except Exception:  # noqa: BLE001
            pass


def _switch_forwards_sqlite(cursor):
    cursor.execute("PRAGMA foreign_keys=OFF")
    try:
        _sqlite_rebuild_cat_medicos(cursor, promote_id=True)

        for table, medico_col, legacy_col, _pk_col in FK_COLUMNS:
            cursor.execute(
                f'UPDATE "{table}" SET "{medico_col}" = ('
                f'  SELECT m.id FROM cat_medicos m WHERE m.id_usuario = "{table}"."{legacy_col}"'
                f') WHERE "{legacy_col}" IS NOT NULL'
            )

        for table in dict.fromkeys(t for t, *_ in FK_COLUMNS):
            _sqlite_repoint_fk(cursor, table, ref_table="cat_medicos", old_col="id_usuario", new_col="id")

        errors = []
        for table, medico_col, _legacy_col, pk_col in FK_COLUMNS:
            cursor.execute(
                f'SELECT "{pk_col}" FROM "{table}" t WHERE t."{medico_col}" IS NOT NULL '
                f'AND NOT EXISTS (SELECT 1 FROM cat_medicos m WHERE m.id = t."{medico_col}") LIMIT 50'
            )
            bad = [r[0] for r in cursor.fetchall()]
            if bad:
                errors.append(
                    f"{table}.{medico_col}: {len(bad)} fila(s) sin match en cat_medicos.id "
                    f"tras el switch. PKs (máx 50): {bad}"
                )
        if errors:
            raise RuntimeError("0007_switch_surrogate_pk (sqlite): " + "; ".join(errors))
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")


def _switch_backwards_sqlite(cursor):
    cursor.execute("PRAGMA foreign_keys=OFF")
    try:
        for table, medico_col, legacy_col, _pk_col in FK_COLUMNS:
            cursor.execute(f'UPDATE "{table}" SET "{medico_col}" = "{legacy_col}"')

        for table in dict.fromkeys(t for t, *_ in FK_COLUMNS):
            _sqlite_repoint_fk(cursor, table, ref_table="cat_medicos", old_col="id", new_col="id_usuario")

        _sqlite_rebuild_cat_medicos(cursor, promote_id=False)
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")


# ─── Entry points ─────────────────────────────────────────────────────────

def switch_forwards(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            _switch_forwards_postgres(cursor)
        else:
            _switch_forwards_sqlite(cursor)


def switch_backwards(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            _switch_backwards_postgres(cursor)
        else:
            _switch_backwards_sqlite(cursor)


class Migration(migrations.Migration):

    dependencies = [
        ("medicos", "0006_backfill_legacy_ids"),
    ]

    # F4-08 (D9/R2 -- CORREGIDO en esta sesión, ver Engram
    # sdd/medico-pk-independiente/design): el diseño original ponía acá un
    # `run_before = [("almacen_insumos", "0002_medico_fk_integrity")]` para
    # forzar a que este switch corriera ANTES que ese RunPython en un plan
    # de migraciones desde cero. Se retiró: declarar esa arista agrega una
    # dependencia en el GRAFO de migraciones que Django valida contra el
    # HISTORIAL real de cada base (`InconsistentMigrationHistory`). Cualquier
    # base existente que ya tuviera `almacen_insumos.0002` aplicada (que es
    # el caso normal, esa migración es muy anterior a este cambio) queda
    # rota: `makemigrations`/`migrate` se niegan a correr porque el orden
    # aplicado contradice el orden declarado -- no es un problema del
    # entorno de un desarrollador puntual, rompe a CUALQUIER DB con ese
    # historial.
    #
    # La razón por la que el `run_before` ya no hace falta: `almacen_insumos
    # /0002_medico_fk_integrity` (F4-12) fue blindado para resolver
    # `medico.id_usuario_id` explícitamente, NUNCA `medico.pk` -- así que su
    # RunPython es semánticamente correcto sin importar si corre antes o
    # después de este switch (antes: pk == id_usuario, da lo mismo; después:
    # pk pasa a ser `id`, pero el código nunca lee `pk`, lee el campo
    # `id_usuario_id` por nombre). La defensa en profundidad de F4-12 alcanza
    # sola; la arista declarativa era redundante y además insegura para DBs
    # existentes. Para una base NUEVA (desde cero), la única red de
    # seguridad respecto del orden de aplicación pasa a ser el gate de CI
    # D3 (migración desde cero), no una dependencia declarada acá.
    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # Orden deliberado (demover antes de promover): evita que el
                # estado intermedio de la migración represente dos campos
                # con primary_key=True a la vez en CatMedico.
                migrations.AlterField(
                    model_name="catmedico",
                    name="id_usuario",
                    field=models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="authentication.syusuario",
                        db_column="id_usuario",
                        related_name="medico",
                    ),
                ),
                migrations.AddField(
                    model_name="catmedico",
                    name="id",
                    field=models.BigAutoField(primary_key=True, serialize=False),
                ),
                # Cierre de R5 -- nombre a mostrar cuando id_usuario es NULL
                # (médico sin usuario). Ver identity.display_name().
                migrations.AddField(
                    model_name="catmedico",
                    name="nombre_display",
                    field=models.CharField(max_length=200, null=True, blank=True),
                ),
                # Las 9 FKs entrantes NO necesitan AlterField de estado: no
                # declaran `to_field`, así que Django resuelve su target
                # dinámicamente contra `CatMedico._meta.pk` (ya `id` tras
                # las dos operaciones de arriba). Ver cabecera del archivo.
            ],
            database_operations=[
                migrations.RunPython(switch_forwards, switch_backwards),
            ],
        ),
    ]
