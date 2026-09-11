# ConsumoConsulta.medico era CharField libre (nombre tipeado/autocompletado
# en el frontend, pero nunca forzado a existir en el catalogo de medicos).
# Se convierte a FK real hacia medicos.CatMedico. paciente e id_cita quedan
# sin tocar -- ver memoria del proyecto (sires/db-integrity/consumoconsulta-pendiente):
# paciente es texto libre sin catalogo real posible, e id_cita esta muerto
# en el frontend actual, sin evidencia de a que tabla deberia apuntar.
#
# 0 filas reales verificadas en esta tabla -- igual se backfillea por
# nombre completo (case-insensitive) por las dudas de produccion, y se
# frena con el detalle si algo no matchea en vez de perder el dato.
#
# F4-12 (medico-pk-independiente, D9/R2): este RunPython usaba `medico.pk`
# asumiendo implicitamente que `pk == id_usuario` (cierto SOLO mientras
# `id_usuario` sea la PK de CatMedico). Desde `medicos/0007_switch_surrogate_pk.py`
# la PK pasa a ser `id` (surrogate), lo que cambiaria en silencio el valor
# que este backfill asigna a `ConsumoConsulta.medico_id` si esta migracion
# llegara a correr DESPUES del switch en un plan desde cero. Se blinda
# usando `medico.id_usuario_id` explicitamente (funciona en ambos mundos,
# antes y despues del switch, porque el modelo historico expone el campo
# por nombre) -- defensa en profundidad ademas de `run_before` en 0007.
import django.db.models.deletion
from django.db import migrations, models


def backfill_medico_fk(apps, schema_editor):
    ConsumoConsulta = apps.get_model("almacen_insumos", "ConsumoConsulta")
    CatMedico = apps.get_model("medicos", "CatMedico")

    catalogo_por_nombre = {}
    for medico in CatMedico.objects.select_related("id_usuario__detalle"):
        detalle = getattr(medico.id_usuario, "detalle", None)
        if detalle and detalle.nombre_completo:
            catalogo_por_nombre.setdefault(
                detalle.nombre_completo.strip().upper(), []
            ).append(medico.id_usuario_id)

    sin_match = []
    for consumo in ConsumoConsulta.objects.exclude(medico_legacy=""):
        clave = (consumo.medico_legacy or "").strip().upper()
        candidatos = catalogo_por_nombre.get(clave, [])
        if len(candidatos) != 1:
            sin_match.append((consumo.pk, consumo.medico_legacy, len(candidatos)))
            continue
        consumo.medico_id = candidatos[0]
        consumo.save(update_fields=["medico"])

    if sin_match:
        detalle = ", ".join(
            f"consumo #{pk} (medico={valor!r}, matches={n})" for pk, valor, n in sin_match
        )
        raise RuntimeError(
            "No se pudo mapear 'medico' a medicos.CatMedico (sin match unico) para: "
            f"{detalle}. Corrige el dato o desambigua manualmente y vuelve a correr la migracion."
        )


def backfill_medico_fk_reverse(apps, schema_editor):
    ConsumoConsulta = apps.get_model("almacen_insumos", "ConsumoConsulta")
    for consumo in ConsumoConsulta.objects.select_related("medico__id_usuario__detalle").all():
        detalle = getattr(consumo.medico.id_usuario, "detalle", None) if consumo.medico_id else None
        consumo.medico_legacy = detalle.nombre_completo if detalle else ""
        consumo.save(update_fields=["medico_legacy"])


class Migration(migrations.Migration):

    dependencies = [
        ("almacen_insumos", "0001_initial"),
        ("medicos", "0003_relmedicoconsultoriohorario_canal"),
    ]

    operations = [
        migrations.RenameField(
            model_name="consumoconsulta",
            old_name="medico",
            new_name="medico_legacy",
        ),
        migrations.AddField(
            model_name="consumoconsulta",
            name="medico",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="medicos.catmedico",
                related_name="consumos_insumos",
            ),
        ),
        migrations.RunPython(backfill_medico_fk, backfill_medico_fk_reverse),
        migrations.RemoveField(
            model_name="consumoconsulta",
            name="medico_legacy",
        ),
    ]
