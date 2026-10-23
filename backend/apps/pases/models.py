from django.db import models


class Referral(models.Model):
    """
    Pase/referencia emitido desde una consulta cerrada: Laboratorio,
    Gabinete, Especialidad, Hospitalizacion o Tercer Nivel. Equivalente
    moderno de pas_laboratorio/pas_gabinete/pas_especialidad/pas_hospital/
    pas_institutos del legado (SISEM). Un solo Referral con status=ACTIVO
    por (consultation, referral_type) -- mismo criterio que el legado
    ("solo un pase activo por consulta").
    """

    class ReferralType(models.TextChoices):
        LABORATORIO = "laboratorio", "Laboratorio"
        GABINETE = "gabinete", "Gabinete"
        ESPECIALIDAD = "especialidad", "Especialidad"
        HOSPITALIZACION = "hospitalizacion", "Hospitalización"
        TERCER_NIVEL = "tercer_nivel", "Tercer Nivel"

    class VisitType(models.TextChoices):
        PRIMERA_VEZ = "primera_vez", "Primera Vez"
        SUBSECUENTE = "subsecuente", "Subsecuente"

    class Status(models.TextChoices):
        ACTIVO = "activo", "Activo"
        CANCELADO = "cancelado", "Cancelado"

    id_referral = models.BigAutoField(primary_key=True, db_column="id_pase")
    consultation = models.ForeignKey(
        "consulta_medica.VisitConsultation",
        db_column="id_consulta",
        on_delete=models.PROTECT,
        related_name="referrals",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    # Plan identidad, Fase 5: el registro (afiliacion) atendido. Se resuelve
    # solo al guardar: consulta_medica.services.operational_link_service.
    patient = models.ForeignKey(
        "consulta_medica.Patient", db_column="id_paciente", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )

    referral_type = models.CharField(
        max_length=20, db_column="tipo_pase", choices=ReferralType.choices,
    )
    # Especialidad, Hospitalizacion y Tercer Nivel usan destination_center
    # (catalogos.CatCentroAtencion, incluyendo el choice INSTITUTO agregado
    # para cubrir Tercer Nivel sin crear un catalogo nuevo). Laboratorio y
    # Gabinete lo dejan null -- su destino vive en ReferralStudyDetail.
    destination_center = models.ForeignKey(
        "catalogos.CatCentroAtencion",
        db_column="id_centro_destino",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    # Especialidad la usa como la especialidad solicitada; Hospitalizacion
    # la reusa como "tipo de servicio" (equivalente al cat_tphospi del
    # legado, que en la practica es casi siempre un servicio/especialidad).
    specialty = models.ForeignKey(
        "catalogos.Especialidades",
        db_column="id_especialidad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    requested_care = models.TextField(
        db_column="atencion_solicitada", null=True, blank=True,
    )
    # Describe la cita EN el destino (hospital/instituto receptor), no la
    # consulta actual -- mismo matiz que tp_cita en el legado.
    visit_type = models.CharField(
        max_length=20, db_column="tp_cita", choices=VisitType.choices,
        null=True, blank=True,
    )
    folio = models.CharField(max_length=32, db_column="folio", unique=True)
    status = models.CharField(
        max_length=20, db_column="estatus", choices=Status.choices,
        default=Status.ACTIVO,
    )
    # Motivo obligatorio al cancelar -- mismo patron ya aplicado a
    # CitaMedica/Visit (VISIT_MOTIVO_REQUERIDO / CITA_MOTIVO_REQUERIDO),
    # reusando el mismo catalogo tipificado en vez de texto libre.
    cancellation_reason = models.ForeignKey(
        "catalogos.MotivoCita",
        db_column="id_motivo_cancelacion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "ref_referral"
        constraints = [
            models.UniqueConstraint(
                fields=["consultation", "referral_type"],
                condition=models.Q(status="activo"),
                name="ref_referral_one_active_per_type",
            ),
        ]
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="ref_referral_patient_idx"),
            models.Index(fields=["is_active"], name="ref_referral_active_idx"),
        ]


class ReferralStudyDetail(models.Model):
    """
    Detalle 1:N de un Referral tipo Laboratorio/Gabinete -- un mismo pase
    puede pedir varios estudios (equivalente a det_paslab/det_pasgab del
    legado). cost_approved/valid_until son version simplificada de la
    aprobacion por costo y vigencia de canje que tenia el legado
    (AutorizaD().PaseLG + ope_param col. 6) -- sin motor de autorizacion
    externo por ahora.
    """

    id_referral_study = models.BigAutoField(
        primary_key=True, db_column="id_pase_estudio",
    )
    referral = models.ForeignKey(
        Referral, db_column="id_pase", on_delete=models.PROTECT,
        related_name="study_details",
    )
    study_type = models.ForeignKey(
        "catalogos.EstudiosMed", db_column="id_estudio",
        on_delete=models.PROTECT, related_name="+",
    )
    cost_approved = models.BooleanField(db_column="costo_aprobado", default=False)
    valid_until = models.DateField(db_column="vigente_hasta", null=True, blank=True)
    status = models.CharField(
        max_length=20, db_column="estatus",
        choices=Referral.Status.choices, default=Referral.Status.ACTIVO,
    )

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "ref_referral_study"
        indexes = [
            models.Index(fields=["referral"], name="ref_refstudy_referral_idx"),
        ]
