"""
5.2 paso 3: HABITO como el documento.

- desde: fecha -> anio (smallint). Postgres no convierte date a smallint con un
  ALTER simple, asi que va por columna temporal: se copia el anio, se borra la
  fecha y se renombra. No se pierde nada: el documento pide solo el anio.
- hasta (anio en que lo dejo) y estado N (lo niega).
- sw_status A vigente / B anterior, con UNA fila vigente por paciente y habito.
  Antes de crear el indice unico, los duplicados vigentes que ya existan se
  resuelven: queda vigente el mas reciente y los demas pasan a B (historial),
  sin borrar ninguno.
"""
import datetime

from django.db import migrations, models


def copy_since_year(apps, schema_editor):
    Habit = apps.get_model("consulta_medica", "Habit")
    for habit in Habit.objects.exclude(since__isnull=True).only("pk", "since"):
        Habit.objects.filter(pk=habit.pk).update(since_year=habit.since.year)


def copy_since_date(apps, schema_editor):
    # Reversa: el anio vuelve como 1 de enero (el dia y mes no existen ya).
    Habit = apps.get_model("consulta_medica", "Habit")
    for habit in Habit.objects.exclude(since_year__isnull=True).only("pk", "since_year"):
        Habit.objects.filter(pk=habit.pk).update(since=datetime.date(habit.since_year, 1, 1))


def keep_latest_current(apps, schema_editor):
    Habit = apps.get_model("consulta_medica", "Habit")
    current = (
        Habit.objects.filter(record_status="A", is_active=True)
        .order_by("no_exp", "pk_num", "habit_id", "-created_at", "-pk")
        .values_list("pk", "no_exp", "pk_num", "habit_id")
    )
    seen, previous_ids = set(), []
    for pk, no_exp, pk_num, habit_id in current:
        key = (no_exp, pk_num, habit_id)
        if key in seen:
            previous_ids.append(pk)
        else:
            seen.add(key)
    if previous_ids:
        Habit.objects.filter(pk__in=previous_ids).update(record_status="B")


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0047_antecedentes_sw_presente"),
    ]

    operations = [
        # desde: fecha -> anio
        migrations.AddField(
            model_name="habit",
            name="since_year",
            field=models.PositiveSmallIntegerField(blank=True, db_column="desde_anio", null=True),
        ),
        migrations.RunPython(copy_since_year, copy_since_date),
        migrations.RemoveField(model_name="habit", name="since"),
        migrations.RenameField(model_name="habit", old_name="since_year", new_name="since"),
        migrations.AlterField(
            model_name="habit",
            name="since",
            field=models.PositiveSmallIntegerField(blank=True, db_column="desde", null=True),
        ),
        # hasta + estado N
        migrations.AddField(
            model_name="habit",
            name="until",
            field=models.PositiveSmallIntegerField(blank=True, db_column="hasta", null=True),
        ),
        migrations.AlterField(
            model_name="habit",
            name="status",
            field=models.CharField(
                choices=[("N", "Lo niega"), ("A", "Actual"), ("E", "Lo dejo")],
                db_column="estado", default="A", max_length=1,
            ),
        ),
        # una fila vigente por paciente y habito
        migrations.AddField(
            model_name="habit",
            name="record_status",
            field=models.CharField(
                choices=[("A", "Vigente"), ("B", "Anterior")], db_column="sw_status", default="A", max_length=1,
            ),
        ),
        migrations.RunPython(keep_latest_current, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="habit",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True), ("record_status", "A")),
                fields=("no_exp", "pk_num", "habit"),
                name="cns_habito_vigente_uq",
            ),
        ),
    ]
