# FASE 3 (MIGRATE/BACKFILL) del cambio `medico-pk-independiente` -- ver
# Engram, sdd/medico-pk-independiente/design, sección 3.
#
# Código de aplicación SIN TOCAR todavía. Copia `medico_id -> medico_id_legacy`
# (y las dos columnas de `rel_medico_cobertura`) y valida con el MISMO
# criterio "frenar con el detalle en vez de perder el dato" que ya usa
# `almacen_insumos/0002_medico_fk_integrity.py`, precedente del repo.
#
# Las columnas `*_legacy` son puramente físicas (no están en el estado de
# Django, ver 0004_expand_surrogate_pk.py) -- por eso este backfill es SQL
# crudo, no `Table.objects.update()`. El UPDATE es una copia dentro de la
# misma fila (sin JOIN), sintaxis idéntica en Postgres y SQLite -- no hace
# falta ramificar por vendor acá (a diferencia de 0004/0005/0007).
#
# Post-Fase 3 el sistema queda reversible sin downtime: nadie lee las
# columnas nuevas todavía.
from django.db import migrations

# (tabla, columna_medico, columna_legacy, columna_pk) -- mismo inventario de
# 9 columnas/8 modelos que 0004_expand_surrogate_pk.py (LEGACY_MIRROR_COLUMNS),
# acá con el nombre de la columna PK física agregado para poder reportar
# filas concretas en un aborto (criterio 2/3 del design).
FK_COLUMNS = [
    ("rel_medico_especialidad", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_centro", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_consultorio", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_excepcion", "medico_id", "medico_id_legacy", "id"),
    ("rel_medico_cobertura", "medico_suplente_id", "medico_suplente_id_legacy", "id"),
    ("rel_medico_cobertura", "medico_titular_id", "medico_titular_id_legacy", "id"),
    ("citas_medicas", "medico_id", "medico_id_legacy", "id"),
    ("citas_horarios_disponibles", "medico_id", "medico_id_legacy", "id"),
    # NOTA (post-mortem, 2026-09-10): el error "no existe la columna
    # «medico_id»" que motivó un cambio equivocado acá NO era un problema de
    # naming -- era que `almacen_insumos/0002_medico_fk_integrity.py` estaba
    # marcada como aplicada en `django_migrations` (schema "sires") pero
    # nunca corrió de verdad contra esa tabla: `sires.almacen_consumos_consulta`
    # seguía con la columna vieja `medico` (CharField libre, character
    # varying), no con el FK `medico_id` (bigint). Se resolvió re-aplicando
    # 0002 de verdad (fake-revert a 0001 + migrate real) en vez de apuntar
    # este backfill a la columna de texto. Esta tabla SÍ sigue la convención
    # default `<campo>_id` como las otras 8.
    ("almacen_consumos_consulta", "medico_id", "medico_id_legacy", "id_consumo"),
]


def backfill_forwards(apps, schema_editor):
    connection = schema_editor.connection
    errors: list[str] = []

    with connection.cursor() as cursor:
        # Copia medico_id -> medico_id_legacy para las filas con medico_id
        # cargado (F3-01).
        for table, medico_col, legacy_col, _pk_col in FK_COLUMNS:
            cursor.execute(
                f'UPDATE "{table}" SET "{legacy_col}" = "{medico_col}" '
                f'WHERE "{medico_col}" IS NOT NULL;'
            )

        # F3-02 -- criterios 1-3 del design, por tabla.
        for table, medico_col, legacy_col, pk_col in FK_COLUMNS:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{medico_col}" IS NOT NULL')
            count_medico = cursor.fetchone()[0]
            cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{legacy_col}" IS NOT NULL')
            count_legacy = cursor.fetchone()[0]

            # Criterio 1: los conteos deben calzar exactamente.
            if count_medico != count_legacy:
                errors.append(
                    f"{table}.{legacy_col}: COUNT(medico_id NOT NULL)={count_medico} != "
                    f"COUNT(medico_id_legacy NOT NULL)={count_legacy}"
                )

            # Criterio 2: fila con medico_id NOT NULL y legacy NULL (máx 50 PKs).
            cursor.execute(
                f'SELECT "{pk_col}" FROM "{table}" '
                f'WHERE "{medico_col}" IS NOT NULL AND "{legacy_col}" IS NULL LIMIT 50'
            )
            orphan_pks = [row[0] for row in cursor.fetchall()]
            if orphan_pks:
                errors.append(
                    f"{table}: fila(s) con {medico_col} NOT NULL y {legacy_col} NULL. "
                    f"PKs (máx 50): {orphan_pks}"
                )

            # Criterio 3: medico_id_legacy sin match futuro en cat_medicos.id_usuario.
            cursor.execute(
                f'SELECT t."{pk_col}", t."{legacy_col}" FROM "{table}" t '
                f'WHERE t."{legacy_col}" IS NOT NULL '
                f'AND NOT EXISTS (SELECT 1 FROM cat_medicos m WHERE m.id_usuario = t."{legacy_col}") '
                f'LIMIT 50'
            )
            unmatched = cursor.fetchall()
            if unmatched:
                errors.append(
                    f"{table}: {legacy_col} sin match en cat_medicos.id_usuario "
                    f"(mapeo futuro imposible). (pk, valor) máx 50: {unmatched}"
                )

        # Criterio 4: la secuencia de cat_medicos.id no pobló alguna fila.
        cursor.execute("SELECT COUNT(*) FROM cat_medicos WHERE id IS NULL")
        null_ids = cursor.fetchone()[0]
        if null_ids:
            errors.append(f"cat_medicos: {null_ids} fila(s) con id NULL (la secuencia no pobló).")

        # Criterio 5: cat_medicos.id duplicado.
        cursor.execute("SELECT id, COUNT(*) FROM cat_medicos GROUP BY id HAVING COUNT(*) > 1")
        dup_ids = cursor.fetchall()
        if dup_ids:
            errors.append(f"cat_medicos: id duplicado para {dup_ids[:20]}")

    # Criterio 6: re-correr check_medico_identity (A1-A7). Se importa la
    # función pura `run_checks()` (no el Command) para no acoplar esta
    # migración al ciclo de vida de un management command.
    from apps.medicos.management.commands.check_medico_identity import run_checks

    aborts, _warnings = run_checks()
    if aborts:
        errors.extend(f"check_medico_identity: {a}" for a in aborts)

    if errors:
        detalle = "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(
            "0006_backfill_legacy_ids: backfill abortado (nada se perdió, la "
            f"transacción se revierte). Hallazgos:\n{detalle}"
        )


def backfill_backwards(apps, schema_editor):
    # Reverse funcional: vacía las columnas legacy, dejando el estado
    # exactamente como lo dejó 0004 (columnas presentes, NULL).
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        for table, _medico_col, legacy_col, _pk_col in FK_COLUMNS:
            cursor.execute(f'UPDATE "{table}" SET "{legacy_col}" = NULL;')


class Migration(migrations.Migration):

    dependencies = [
        ("medicos", "0005_uniq_id_usuario"),
    ]

    operations = [
        migrations.RunPython(backfill_forwards, backfill_backwards),
    ]
