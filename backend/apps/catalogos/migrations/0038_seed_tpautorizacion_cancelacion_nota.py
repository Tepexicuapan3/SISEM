"""
Siembra el tipo de autorizacion "CN" (cancelacion de nota) en
cat_tpautorizacion (change cancelacion-nota-cascada).

Idempotente por CODIGO (cve_tpautorizacion):
  - si no existe "CN": se crea;
  - si existe "CN" y su nombre es claramente el de cancelacion de nota: se
    reutiliza (y se reactiva si estaba dada de baja);
  - si existe "CN" con OTRO significado (p. ej. un tipo legado distinto): la
    migracion FALLA con un mensaje explicito. NO se reutiliza en silencio
    porque entonces cualquier designacion de ese tipo habilitaria cancelar
    notas por error. Resolver renombrando/recodificando ese tipo en el
    catalogo y reintentar `migrate`.

Reverse: no-op (la fila puede estar referenciada por designaciones).
"""
import unicodedata

from django.db import migrations

CODE = "CN"
NAME = "Cancelación de nota"


def _norm(value):
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().split())


def _is_cancel_note_name(name):
    normalized = _norm(name)
    return "cancel" in normalized and "nota" in normalized


def seed_tp_autorizacion_cn(apps, schema_editor):
    TpAutorizacion = apps.get_model("catalogos", "TpAutorizacion")

    existing = list(TpAutorizacion.objects.filter(code=CODE).order_by("pk"))
    if not existing:
        TpAutorizacion.objects.create(code=CODE, name=NAME)
        return

    matching = [row for row in existing if _is_cancel_note_name(row.name)]
    if not matching:
        found = ", ".join(f"id={row.pk} nombre={row.name!r}" for row in existing)
        raise RuntimeError(
            f"catalogos.0038: ya existe en cat_tpautorizacion un tipo con codigo "
            f"{CODE!r} que NO corresponde a 'cancelacion de nota' ({found}). "
            f"No se reutiliza para evitar habilitar cancelaciones por error. "
            f"Cambie el codigo de ese tipo (o elija otro codigo y ajuste "
            f"TIPO_CANCELAR_NOTA) y vuelva a ejecutar migrate."
        )

    row = matching[0]
    if not row.is_active or row.deleted_at is not None:
        row.is_active = True
        row.deleted_at = None
        row.deleted_by_id = None
        row.save(update_fields=["is_active", "deleted_at", "deleted_by_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0037_designacion_autorizador"),
    ]

    operations = [
        migrations.RunPython(seed_tp_autorizacion_cn, migrations.RunPython.noop),
    ]
