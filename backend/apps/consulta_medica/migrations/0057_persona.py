"""
Plan identidad del paciente, Fase 3 (expandir): cns_persona y
cns_paciente.id_persona (todavia opcional), llenado con UNA persona por
registro y el MISMO uuid que ya tiene cada paciente (no se rompe ninguna
referencia externa). Sin cambio visible: hoy cada persona tiene un solo
registro. 0058 vuelve obligatoria la columna: va aparte porque en Postgres
llenar filas y alterar la columna en la misma transaccion falla con
"pending trigger events".
"""
import uuid

import django.db.models.deletion
from django.db import migrations, models

LOTE = 5000


def llenar(apps, schema_editor):
    Patient = apps.get_model("consulta_medica", "Patient")
    Person = apps.get_model("consulta_medica", "Person")

    pendientes = Patient.objects.filter(person__isnull=True).values_list("uuid", flat=True)
    lote = []
    for valor in pendientes.iterator(chunk_size=LOTE):
        lote.append(Person(uuid=valor))
        if len(lote) >= LOTE:
            Person.objects.bulk_create(lote)
            lote = []
    if lote:
        Person.objects.bulk_create(lote)

    q = schema_editor.quote_name
    paciente, persona = Patient._meta.db_table, Person._meta.db_table
    schema_editor.execute(
        f"UPDATE {q(paciente)} SET {q('id_persona')} = "
        f"(SELECT p.{q('id_persona')} FROM {q(persona)} p WHERE p.{q('uuid')} = {q(paciente)}.{q('uuid')}) "
        f"WHERE {q('id_persona')} IS NULL"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0056_sexo_convencion_sermed"),
    ]

    operations = [
        migrations.CreateModel(
            name="Person",
            fields=[
                ("id_person", models.BigAutoField(db_column="id_persona", primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(db_column="uuid", default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="fch_alta")),
                ("created_by_id", models.BigIntegerField(blank=True, db_column="usr_alta", null=True)),
            ],
            options={"db_table": "cns_persona"},
        ),
        migrations.AddField(
            model_name="patient",
            name="person",
            field=models.ForeignKey(
                db_column="id_persona", null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="records", to="consulta_medica.person",
            ),
        ),
        migrations.RunPython(llenar, migrations.RunPython.noop),
    ]
