# Visit.doctor_id vivia como entero suelto aunque siempre referencio a
# authentication.SyUsuario (la aplicacion siempre lo trato como un id de
# usuario, nunca como texto, via visit_repository.py / ficha_service.py).
#
# F5-06 (medico-pk-independiente, obs #473): Visit.doctor sigue apuntando a
# SyUsuario a proposito -- NO se reapunta a medicos.CatMedico (fuera de
# alcance de ese cambio, ver propuesta obs #467 seccion 2 "Fuera del
# alcance"). Es "que usuario atendio", no "que medico del catalogo". El
# codigo que traduce entre `Visit.doctor_id` (espacio usuario) y
# `medico_id` (espacio CatMedico, PK propia desde medicos/0007_switch_surrogate_pk.py)
# vive en `apps.medicos.identity` -- ver esa migracion y
# `apps/recepcion/uses_case/qr_checkin_usecase.py`.
#
# La verificacion de "0 huerfanos" original corrio contra datos de
# desarrollo, no contra produccion -- en produccion SI hay filas de
# rcp_visits con doctor_id apuntando a un SyUsuario que ya no existe
# (medico dado de baja/eliminado sin limpiar la referencia). El intento
# de aplicar el AlterField sin este backfill fallo con IntegrityError
# (ver incidente: doctor_id=120 no presente en sy_usuarios). Postgres
# revirtio la migracion completa al fallar -- no hubo perdida de datos.
#
# Este backfill deja en NULL cualquier doctor_id huerfano ANTES de crear
# la constraint. Es coherente con on_delete=SET_NULL de mas abajo: un
# doctor_id que ya no existe es exactamente el caso que SET_NULL esta
# pensado para representar.
#
# db_column="doctor_id" se mantiene identico, asi que el RenameField no
# genera SQL de columna -- el AlterField que sigue solo agrega la
# constraint FK sobre los valores ya cargados. El indice compuesto se
# recrea porque el nombre del campo Python cambio (la columna fisica no).
import django.db.models.deletion
from django.db import migrations, models


def _null_orphan_doctor_ids(apps, schema_editor):
    Visit = apps.get_model("recepcion", "Visit")
    SyUsuario = apps.get_model("authentication", "SyUsuario")

    valid_ids = set(SyUsuario.objects.values_list("id_usuario", flat=True))
    orphans = list(
        Visit.objects.exclude(doctor_id__isnull=True)
        .exclude(doctor_id__in=valid_ids)
        .values_list("id_visit", "folio", "doctor_id")
    )

    if not orphans:
        return

    print(
        f"[0019_doctor_fk_integrity] {len(orphans)} visita(s) con doctor_id "
        "huerfano -- se ponen en NULL antes de crear la constraint FK:"
    )
    for visit_id, folio, doctor_id in orphans:
        print(f"  - visit id_visit={visit_id} folio={folio} doctor_id={doctor_id} (no existe en sy_usuarios)")

    Visit.objects.filter(id_visit__in=[row[0] for row in orphans]).update(doctor_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("recepcion", "0018_horariodisponible_idx_consultorio_fecha_canal"),
        ("authentication", "0012_remove_detusuario_tipo_personal_text"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="visit",
            name="rcp_visits_doc_status_idx",
        ),
        migrations.RunPython(_null_orphan_doctor_ids, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="visit",
            old_name="doctor_id",
            new_name="doctor",
        ),
        migrations.AlterField(
            model_name="visit",
            name="doctor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="authentication.syusuario",
                db_column="doctor_id",
                related_name="visitas_atendidas",
            ),
        ),
        migrations.AddIndex(
            model_name="visit",
            index=models.Index(fields=["doctor", "status"], name="rcp_visits_doc_status_idx"),
        ),
    ]
