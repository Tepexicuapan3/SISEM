"""
Copia CONDICIONAL de cat_autorizadores a designaciones (change
cancelacion-nota-cascada).

Solo actua si la tabla fisica `cat_autorizadores` existe Y tiene filas; si no
existe (BD fresca: 0013 ya no la crea) o esta vacia, no hace nada
(0 designaciones).

Por cada par (usuario, tipo de autorizacion) con filas vigentes se crea UNA
designacion con un item de alcance CENTRO por cada centro distinto. Reglas:
  - NUNCA se lee `pwd_autorizador`: el SELECT enumera columnas y no la incluye.
  - Se copian solo filas vigentes (est_activo y sin fch_baja, si esas columnas
    existen): una baja no debe recuperar poder de autorizar.
  - Vigencia: fe_inicio = fecha de la migracion, fe_fin NULL (CENTRO no exige
    fin). id_autorizador_origen = id de la primera fila del grupo.
  - Si ya existe una designacion activa para (usuario, tipo) solo se agregan
    los centros faltantes (re-ejecucion segura).

Reverse: borra alcances y designaciones con id_autorizador_origen NOT NULL
(las creadas por esta copia). Corre DESPUES del reverse de 0040, que ya
restauro las filas en cat_autorizadores.
"""
from datetime import date

from django.db import migrations

LEGACY_TABLE = "cat_autorizadores"
REQUIRED_COLUMNS = (
    "id_autorizador",
    "id_centro_atencion",
    "cargo",
    "id_tpautorizacion",
    "id_usuario",
)
OPTIONAL_COLUMNS = ("img_firma", "est_activo", "fch_baja")


def _read_legacy_rows(connection):
    """Devuelve lista de dicts o None si la tabla no existe / esta vacia."""
    if LEGACY_TABLE not in set(connection.introspection.table_names()):
        return None

    qn = connection.ops.quote_name
    with connection.cursor() as cursor:
        present = {
            col.name
            for col in connection.introspection.get_table_description(cursor, LEGACY_TABLE)
        }
        missing = [c for c in REQUIRED_COLUMNS if c not in present]
        if missing:
            raise RuntimeError(
                f"catalogos.0039: {LEGACY_TABLE} no tiene las columnas esperadas "
                f"{missing}; revisar el esquema antes de migrar."
            )
        columns = list(REQUIRED_COLUMNS) + [c for c in OPTIONAL_COLUMNS if c in present]
        # Enumerado a proposito: pwd_autorizador NUNCA se selecciona.
        cursor.execute(
            f"SELECT {', '.join(qn(c) for c in columns)} FROM {qn(LEGACY_TABLE)} "
            f"ORDER BY {qn('id_autorizador')}"
        )
        rows = [dict(zip(columns, values)) for values in cursor.fetchall()]

    if not rows:
        return None
    return rows


def copy_autorizadores(apps, schema_editor):
    rows = _read_legacy_rows(schema_editor.connection)
    if rows is None:
        return

    Designacion = apps.get_model("catalogos", "DesignacionAutorizador")
    Alcance = apps.get_model("catalogos", "DesignacionAlcance")

    groups = {}
    for row in rows:
        activo = row.get("est_activo")
        if (activo is not None and not activo) or row.get("fch_baja") is not None:
            continue
        groups.setdefault((row["id_usuario"], row["id_tpautorizacion"]), []).append(row)

    today = date.today()
    for (user_id, tipo_id), group in groups.items():
        first = group[0]
        designacion = Designacion.objects.filter(
            user_id=user_id,
            authorization_type_id=tipo_id,
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        if designacion is None:
            designacion = Designacion.objects.create(
                user_id=user_id,
                authorization_type_id=tipo_id,
                position=(first["cargo"] or "")[:60],
                start_date=today,
                end_date=None,
                signature_image=first.get("img_firma"),
                origin_authorizer_id=first["id_autorizador"],
            )

        existing_centers = set(
            Alcance.objects.filter(
                designation=designacion,
                scope_type="CENTRO",
                is_active=True,
                deleted_at__isnull=True,
            ).values_list("center_id", flat=True)
        )
        for center_id in dict.fromkeys(r["id_centro_atencion"] for r in group):
            if center_id in existing_centers:
                continue
            Alcance.objects.create(
                designation=designacion,
                scope_type="CENTRO",
                center_id=center_id,
                center_type=None,
            )


def remove_copied_designaciones(apps, schema_editor):
    Designacion = apps.get_model("catalogos", "DesignacionAutorizador")
    Alcance = apps.get_model("catalogos", "DesignacionAlcance")
    copied = Designacion.objects.filter(origin_authorizer_id__isnull=False)
    Alcance.objects.filter(designation__in=copied).delete()
    copied.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0038_seed_tpautorizacion_cancelacion_nota"),
    ]

    operations = [
        migrations.RunPython(copy_autorizadores, remove_copied_designaciones),
    ]
