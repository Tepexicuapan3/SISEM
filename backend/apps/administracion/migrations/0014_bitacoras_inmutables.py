"""
Bitacoras append-only a nivel de base (NOM-024: evidencia no manipulable).
Hasta aqui "no se edita ni se borra" era solo una convencion del codigo;
ahora Postgres rechaza UPDATE, DELETE y TRUNCATE sobre las bitacoras.

Excepciones que el trigger SI deja pasar (no alteran la evidencia):
  - Poner en NULL la FK al usuario cuando Django borra un SyUsuario
    (on_delete=SET_NULL, p. ej. clean_seed_data): el login queda en
    cd_usuario / actor_nombre. Las columnas permitidas van como argumentos
    del trigger.
  - Cerrar una sola vez un registro de bitacora_sync_expediente que sigue
    EN_CURSO (resultado, fecha_fin, conteos, errores).

cns_bitacora_cambios (consulta_medica) se protege en su propia migracion con
esta misma funcion.

En SQLite (tests) no hace nada. Si un DBA necesita corregir algo bajo un
proceso controlado: ALTER TABLE <tabla> DISABLE TRIGGER <nombre>, y dejarlo
documentado.
"""
from django.db import migrations

FUNCION = """
CREATE OR REPLACE FUNCTION sires_bitacora_inmutable() RETURNS trigger AS $$
DECLARE
    libres text[];
BEGIN
    -- Columnas que si pueden cambiar (argumentos de CREATE TRIGGER).
    libres := COALESCE(TG_ARGV, '{}'::text[]);
    IF TG_OP = 'UPDATE' THEN
        IF TG_TABLE_NAME = 'bitacora_sync_expediente'
           AND to_jsonb(OLD) ->> 'resultado' = 'EN_CURSO' THEN
            libres := libres || ARRAY['resultado', 'fecha_fin', 'conteos', 'errores'];
        END IF;
        IF (to_jsonb(NEW) - libres) = (to_jsonb(OLD) - libres) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'La tabla % es una bitacora: no se permite %.', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege',
              HINT = 'Las bitacoras son append-only (NOM-024).';
END;
$$ LANGUAGE plpgsql;
"""

# tabla -> columnas FK con on_delete=SET_NULL que si pueden quedar en NULL.
TABLAS = {
    "bitacora_sync_expediente": ["id_usuario"],
    "bitacora_replica_sermed": [],
    "bitacora_acceso": ["id_usuario"],
    "auditoria_eventos": ["actor_id_usuario", "target_id_usuario", "id_centro_atencion"],
}


def _argumentos(columnas):
    return ", ".join(f"'{c}'" for c in columnas)


def crear_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(FUNCION)
        for tabla, columnas in TABLAS.items():
            cursor.execute(f"DROP TRIGGER IF EXISTS {tabla}_inmutable ON {tabla};")
            cursor.execute(f"DROP TRIGGER IF EXISTS {tabla}_sin_truncate ON {tabla};")
            cursor.execute(
                f"CREATE TRIGGER {tabla}_inmutable BEFORE UPDATE OR DELETE ON {tabla} "
                f"FOR EACH ROW EXECUTE FUNCTION sires_bitacora_inmutable({_argumentos(columnas)});"
            )
            cursor.execute(
                f"CREATE TRIGGER {tabla}_sin_truncate BEFORE TRUNCATE ON {tabla} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION sires_bitacora_inmutable();"
            )


def quitar_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS:
            cursor.execute(f"DROP TRIGGER IF EXISTS {tabla}_inmutable ON {tabla};")
            cursor.execute(f"DROP TRIGGER IF EXISTS {tabla}_sin_truncate ON {tabla};")
        # La funcion la sigue usando cns_bitacora_cambios hasta revertir su
        # migracion (consulta_medica depende de esta, se revierte antes).
        cursor.execute("DROP FUNCTION IF EXISTS sires_bitacora_inmutable();")


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0013_bitacora_sync_expediente"),
    ]

    operations = [
        migrations.RunPython(crear_triggers, quitar_triggers),
    ]
