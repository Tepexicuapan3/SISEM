"""
Agenda quirurgica. Equivalente moderno de det_cirugia/det_cirugcie/
det_cancelaqx del legado (java-main/investigacion/consolidado_assets/sisem/
usuarios/clinicam/body-agendacir.jsp y relacionados).

Diferencias deliberadas frente al legado:
- El folio se genera de forma sincrona en la misma transaccion (igual que
  apps.pases.Referral), por lo que no se replica el token `temporal` que el
  legado usaba para ligar el diagnostico CIE-10 antes de tener folio real.
- `legacy_folio` guarda el `cd_scirugia` original solo como referencia
  textual para una futura carga historica -- NUNCA debe usarse como FK. Si
  algun dia se migra el legado, los catalogos (surgery_type, classification)
  deben resolverse por NOMBRE/descripcion (`cat_cirugias.ds_cirugia`,
  `cat_tpcirugia.ds_tpcirugia`), nunca copiando el ID crudo (`cd_cirugia`,
  `no_consec`), porque esos IDs no corresponden a los catalogos de SISEM.
"""
from django.db import models


class SurgerySchedule(models.Model):
    class Status(models.TextChoices):
        ACTIVA = "activa", "Activa"
        CANCELADA = "cancelada", "Cancelada"

    class PerformedStatus(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        REALIZADA = "realizada", "Realizada"
        NO_REALIZADA = "no_realizada", "No realizada"

    id = models.BigAutoField(primary_key=True, db_column="id_cirugia")
    folio = models.CharField(max_length=32, unique=True, db_column="folio")
    legacy_folio = models.CharField(
        max_length=20, null=True, blank=True, db_column="folio_legado",
    )

    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)

    surgeon = models.ForeignKey(
        "medicos.CatMedico", db_column="id_medico",
        on_delete=models.PROTECT, related_name="+",
    )
    surgery_type = models.ForeignKey(
        "catalogos.CatTipoCirugia", db_column="id_tipo_cirugia",
        on_delete=models.PROTECT, related_name="+",
    )
    classification = models.ForeignKey(
        "catalogos.CatClasificacionCirugia", db_column="id_clasificacion",
        on_delete=models.PROTECT, related_name="+",
    )
    # CharField y NO ForeignKey: CatClinica vive en la base de datos
    # "expedientes" (ver routers.ExpedientesRouter), fisicamente distinta de
    # la BD "default" donde vive este modelo. Postgres no soporta FK entre
    # bases de datos distintas -- mismo patron que Referral.no_exp/pk_num
    # (apps/pases/models.py) y CatClinica.objects.filter(...) en
    # apps/contratos_oxigeno/derechohabiente_service.py. Se valida/resuelve
    # el nombre en la capa de aplicacion (uses_case/repository), no en la DB.
    origin_clinic_id = models.CharField(
        max_length=10, null=True, blank=True, db_column="cd_clinica_origen",
    )

    scheduled_date = models.DateField(db_column="fecha_cirugia")
    scheduled_time = models.TimeField(db_column="hora_cirugia")
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True, db_column="duracion_minutos",
    )

    contact_phone = models.CharField(
        max_length=20, null=True, blank=True, db_column="telefono_contacto",
    )
    description = models.TextField(null=True, blank=True, db_column="descripcion")
    diagnosis_text = models.TextField(
        null=True, blank=True, db_column="diagnostico_texto",
    )
    requirements = models.TextField(
        null=True, blank=True, db_column="requerimientos",
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVA,
        db_column="estatus",
    )
    performed_status = models.CharField(
        max_length=20, choices=PerformedStatus.choices,
        default=PerformedStatus.PENDIENTE, db_column="estatus_realizacion",
    )

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cir_surgery"
        constraints = [
            models.UniqueConstraint(
                fields=["surgeon", "scheduled_date", "scheduled_time"],
                condition=models.Q(status="activa"),
                name="cir_surgery_no_doble_agenda_medico",
            ),
        ]
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="cir_surgery_patient_idx"),
            models.Index(fields=["scheduled_date"], name="cir_surgery_date_idx"),
        ]


class SurgeryDiagnosis(models.Model):
    """Relacion cirugia<->diagnostico CIE-10. Reemplaza det_cirugcie."""

    id = models.BigAutoField(primary_key=True, db_column="id_cirugia_diagnostico")
    surgery = models.ForeignKey(
        SurgerySchedule, db_column="id_cirugia",
        on_delete=models.PROTECT, related_name="diagnoses",
    )
    cie = models.ForeignKey(
        "catalogos.CatCies", db_column="cd_cie",
        on_delete=models.PROTECT, related_name="+",
    )
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)

    class Meta:
        db_table = "cir_surgery_diagnosis"
        constraints = [
            models.UniqueConstraint(
                fields=["surgery", "cie"], name="cir_surgery_diagnosis_uniq",
            ),
        ]


class SurgeryCancellation(models.Model):
    """Bitacora de cancelacion. Reemplaza det_cancelaqx."""

    id = models.BigAutoField(primary_key=True, db_column="id_cirugia_cancelacion")
    surgery = models.ForeignKey(
        SurgerySchedule, db_column="id_cirugia",
        on_delete=models.PROTECT, related_name="cancellations",
    )
    reason = models.ForeignKey(
        "catalogos.CatMotivoCancelacionCirugia", db_column="id_motivo",
        on_delete=models.PROTECT, related_name="+",
    )
    notes = models.TextField(null=True, blank=True, db_column="notas")
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)

    class Meta:
        db_table = "cir_surgery_cancellation"
