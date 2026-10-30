"""
P-03 · Adscripción a consultorio familiar: tablas nuevas que nacen vacías.

Solo agrega (CreateModel). No toca tablas existentes ni copia datos del SISEM
anterior. El trigger que protege el historial y la vista de cambios están en
0033 (solo PostgreSQL).
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0045_parametro_anticipacion_checkin"),
        ("consulta_medica", "0067_borrar_llave_vieja"),
        ("recepcion", "0031_borrar_llave_vieja"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdscripcionClinicaCentro",
            fields=[
                ("id", models.BigAutoField(db_column="id_clinica_centro", primary_key=True, serialize=False)),
                ("clave_clinica_sermed", models.CharField(max_length=10)),
                ("esta_activo", models.BooleanField(default=True)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("id_usuario_creacion", models.BigIntegerField(blank=True, null=True)),
                ("fecha_modificacion", models.DateTimeField(blank=True, null=True)),
                ("id_usuario_modificacion", models.BigIntegerField(blank=True, null=True)),
                ("centro", models.ForeignKey(
                    db_column="id_centro_atencion", on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="catalogos.catcentroatencion",
                )),
            ],
            options={
                "db_table": "adscripcion_clinica_centro",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("clave_clinica_sermed",), name="adscripcion_clinica_centro_clave_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("clave_clinica_sermed", ""), _negated=True),
                        name="adscripcion_clinica_centro_clave_ck",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="AdscripcionConsultorio",
            fields=[
                ("id", models.BigAutoField(db_column="id_adscripcion_consultorio", primary_key=True, serialize=False)),
                ("esta_activo", models.BooleanField(default=True)),
                ("capacidad_maxima", models.IntegerField(blank=True, null=True)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("id_usuario_creacion", models.BigIntegerField(blank=True, null=True)),
                ("fecha_modificacion", models.DateTimeField(blank=True, null=True)),
                ("id_usuario_modificacion", models.BigIntegerField(blank=True, null=True)),
                ("consultorio", models.OneToOneField(
                    db_column="id_consultorio", on_delete=django.db.models.deletion.PROTECT,
                    related_name="adscripcion_config", to="catalogos.consultorios",
                )),
            ],
            options={
                "db_table": "adscripcion_consultorio",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("capacidad_maxima__isnull", True), ("capacidad_maxima__gt", 0), _connector="OR"),
                        name="adscripcion_consultorio_capacidad_ck",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="AdscripcionPaciente",
            fields=[
                ("id", models.BigAutoField(db_column="id_adscripcion", primary_key=True, serialize=False)),
                ("clave_clinica_sermed", models.CharField(max_length=10)),
                ("estatus", models.CharField(
                    choices=[("ACTIVA", "Activa"), ("CERRADA", "Cerrada")], default="ACTIVA", max_length=10,
                )),
                ("origen", models.CharField(
                    choices=[("CHECKIN", "Check-in"), ("CITA", "Cita"), ("MANUAL", "Manual")], max_length=10,
                )),
                ("fue_sugerida", models.BooleanField(default=False)),
                ("motivo_cierre", models.CharField(
                    blank=True, null=True, max_length=20,
                    choices=[
                        ("REASIGNACION", "Reasignación"),
                        ("CAMBIO_CLINICA", "Cambio de clínica en SERMED"),
                        ("CONSULTORIO_INACTIVO", "Consultorio inactivo"),
                        ("UNIFICACION", "Unificación de registros"),
                    ],
                )),
                ("observaciones", models.CharField(blank=True, max_length=255, null=True)),
                ("fecha_inicio", models.DateTimeField(default=django.utils.timezone.now)),
                ("fecha_fin", models.DateTimeField(blank=True, null=True)),
                ("id_usuario_creacion", models.BigIntegerField()),
                ("id_usuario_cierre", models.BigIntegerField(blank=True, null=True)),
                ("centro", models.ForeignKey(
                    db_column="id_centro_atencion", on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="catalogos.catcentroatencion",
                )),
                ("consultorio", models.ForeignKey(
                    db_column="id_consultorio", on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="catalogos.consultorios",
                )),
                ("paciente", models.ForeignKey(
                    db_column="id_paciente", on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="consulta_medica.patient",
                )),
                ("turno", models.ForeignKey(
                    db_column="id_turno", on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="catalogos.turnos",
                )),
            ],
            options={
                "db_table": "adscripcion_paciente",
                "indexes": [
                    models.Index(
                        condition=models.Q(("estatus", "ACTIVA")), fields=["consultorio"],
                        name="adscripcion_paciente_carga_idx",
                    ),
                    models.Index(fields=["paciente", "-fecha_inicio"], name="adscripcion_paciente_hist_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("estatus", "ACTIVA")), fields=("paciente",),
                        name="adscripcion_paciente_una_activa_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("estatus__in", ["ACTIVA", "CERRADA"])),
                        name="adscripcion_paciente_estatus_ck",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("origen__in", ["CHECKIN", "CITA", "MANUAL"])),
                        name="adscripcion_paciente_origen_ck",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("motivo_cierre__isnull", True),
                            ("motivo_cierre__in", ["REASIGNACION", "CAMBIO_CLINICA", "CONSULTORIO_INACTIVO", "UNIFICACION"]),
                            _connector="OR",
                        ),
                        name="adscripcion_paciente_motivo_ck",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("estatus", "ACTIVA"), ("fecha_fin__isnull", True),
                                ("id_usuario_cierre__isnull", True), ("motivo_cierre__isnull", True),
                            ),
                            models.Q(
                                ("estatus", "CERRADA"), ("fecha_fin__isnull", False),
                                ("id_usuario_cierre__isnull", False), ("motivo_cierre__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="adscripcion_paciente_cierre_ck",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("fecha_fin__isnull", True), ("fecha_fin__gte", models.F("fecha_inicio")), _connector="OR",
                        ),
                        name="adscripcion_paciente_fechas_ck",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="AdscripcionCitaAfectada",
            fields=[
                ("id", models.BigAutoField(db_column="id_cita_afectada", primary_key=True, serialize=False)),
                ("estatus", models.CharField(
                    choices=[("PENDIENTE", "Pendiente"), ("REAGENDADA", "Reagendada"), ("DESCARTADA", "Descartada")],
                    default="PENDIENTE", max_length=12,
                )),
                ("motivo_descarte", models.CharField(blank=True, max_length=255, null=True)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_resolucion", models.DateTimeField(blank=True, null=True)),
                ("id_usuario_creacion", models.BigIntegerField()),
                ("id_usuario_resolucion", models.BigIntegerField(blank=True, null=True)),
                ("adscripcion", models.ForeignKey(
                    db_column="id_adscripcion", on_delete=django.db.models.deletion.PROTECT,
                    related_name="citas_afectadas", to="recepcion.adscripcionpaciente",
                )),
                ("cita_cancelada", models.OneToOneField(
                    db_column="id_cita_cancelada", on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="recepcion.citamedica",
                )),
                ("cita_nueva", models.OneToOneField(
                    blank=True, null=True, db_column="id_cita_nueva",
                    on_delete=django.db.models.deletion.PROTECT, related_name="+", to="recepcion.citamedica",
                )),
            ],
            options={
                "db_table": "adscripcion_cita_afectada",
                "indexes": [
                    models.Index(
                        condition=models.Q(("estatus", "PENDIENTE")), fields=["adscripcion"],
                        name="adscripcion_cita_pend_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("estatus__in", ["PENDIENTE", "REAGENDADA", "DESCARTADA"])),
                        name="adscripcion_cita_afectada_estatus_ck",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("cita_nueva__isnull", True), ("estatus", "PENDIENTE"), ("fecha_resolucion__isnull", True)),
                            models.Q(("cita_nueva__isnull", False), ("estatus", "REAGENDADA"), ("fecha_resolucion__isnull", False)),
                            models.Q(
                                ("cita_nueva__isnull", True), ("estatus", "DESCARTADA"),
                                ("fecha_resolucion__isnull", False), ("motivo_descarte__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="adscripcion_cita_afectada_resolucion_ck",
                    ),
                ],
            },
        ),
    ]
