# Mismo fix que recepcion.Visit (ver 0019_doctor_fk_integrity en esa app):
# VisitConsultation.doctor_id era un entero suelto que siempre referencio a
# authentication.SyUsuario (0 huerfanos verificados; consultation_repository
# y los tests ya lo tratan como id de usuario, no como id de medicos.CatMedico).
#
# F5-06 (medico-pk-independiente, obs #473): igual que recepcion.Visit.doctor,
# este campo sigue apuntando a SyUsuario a proposito -- fuera de alcance
# reapuntarlo a medicos.CatMedico (ver propuesta obs #467). La PK de
# CatMedico es propia (`id`) desde medicos/0007_switch_surrogate_pk.py; la
# traduccion entre espacios de id vive en `apps.medicos.identity`.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consulta_medica", "0005_visitconsultation_cie_code"),
        ("authentication", "0012_remove_detusuario_tipo_personal_text"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="visitconsultation",
            name="cns_cons_doc_idx",
        ),
        migrations.RenameField(
            model_name="visitconsultation",
            old_name="doctor_id",
            new_name="doctor",
        ),
        migrations.AlterField(
            model_name="visitconsultation",
            name="doctor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="authentication.syusuario",
                db_column="id_doctor",
                related_name="consultas_atendidas",
            ),
        ),
        migrations.AddIndex(
            model_name="visitconsultation",
            index=models.Index(fields=["doctor"], name="cns_cons_doc_idx"),
        ),
    ]
