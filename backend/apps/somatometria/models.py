from django.db import models


class VisitVitalSigns(models.Model):
    id_vitals = models.BigAutoField(primary_key=True, db_column="id_vitals")
    id_visit = models.OneToOneField(
        "recepcion.Visit",
        db_column="id_visit",
        on_delete=models.CASCADE,
        related_name="vital_signs",
    )
    # Plan identidad, Fase 5: el registro (afiliacion) atendido, copiado de la
    # visita al crear (VitalsRepository.create_for_visit). Desde C7 es lo unico
    # que identifica al paciente en esta tabla.
    patient = models.ForeignKey(
        "consulta_medica.Patient", db_column="id_paciente",
        on_delete=models.PROTECT, related_name="+",
    )
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, db_column="weight_kg")
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, db_column="height_cm")
    temperature_c = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        db_column="temperature_c",
        null=True,
        blank=True,
    )
    oxygen_saturation_pct = models.PositiveSmallIntegerField(
        db_column="oxygen_saturation_pct",
        null=True,
        blank=True,
    )
    heart_rate_bpm = models.PositiveSmallIntegerField(
        db_column="heart_rate_bpm",
        null=True,
        blank=True,
    )
    respiratory_rate_bpm = models.PositiveSmallIntegerField(
        db_column="respiratory_rate_bpm",
        null=True,
        blank=True,
    )
    blood_pressure_systolic = models.PositiveSmallIntegerField(
        db_column="blood_pressure_systolic",
        null=True,
        blank=True,
    )
    blood_pressure_diastolic = models.PositiveSmallIntegerField(
        db_column="blood_pressure_diastolic",
        null=True,
        blank=True,
    )
    waist_circumference_cm = models.PositiveSmallIntegerField(
        db_column="waist_circumference_cm",
        null=True,
        blank=True,
    )
    bmi = models.DecimalField(max_digits=6, decimal_places=2, db_column="bmi")
    glucosa_capilar_mgdl = models.PositiveSmallIntegerField(
        db_column="glucosa_capilar_mgdl",
        null=True,
        blank=True,
    )
    notes = models.CharField(max_length=255, db_column="notes", null=True, blank=True)
    reused_from_visit = models.ForeignKey(
        "recepcion.Visit",
        db_column="reused_from_visit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reused_vital_signs",
        help_text=(
            "Visita origen cuando esta captura reusa signos vitales tomados "
            "hoy en otra visita del mismo paciente (trazabilidad NOM-024). "
            "El servidor NUNCA copia valores del origen: los que se guardan "
            "aca son siempre los que vienen en el payload de esta captura."
        ),
    )
    captured_by = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="captured_by",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vitals_capturados",
        help_text=(
            "Usuario que tomo la medicion original (atribucion NOM-024). "
            "Nunca se reasigna en una correccion posterior -- ver "
            "`updated_by`."
        ),
    )
    updated_by = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="updated_by",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vitals_editados",
        help_text=(
            "Usuario que corrigio la medicion via edicion auditada "
            "(Fase 3). `null` mientras la fila nunca fue corregida -- "
            "nunca pisa a `captured_by`."
        ),
    )
    fch_alta = models.DateTimeField(auto_now_add=True, db_column="fch_alta")
    fch_modf = models.DateTimeField(auto_now=True, db_column="fch_modf")

    class Meta:
        db_table = "smt_visit_vitals"
        indexes = [
            models.Index(fields=["fch_alta"], name="smt_visit_vitals_fchalta_idx"),
        ]


class PatientLatestVitals(models.Model):
    """
    Ultima captura de signos vitales POR INTEGRANTE DEL NUCLEO FAMILIAR
    (`no_exp` + `pk_num`) -- una sola fila que se sobreescribe en cada
    consulta nueva. Es un espejo/cache de conveniencia para precargar el
    formulario de la siguiente consulta, NUNCA la fuente de verdad del
    expediente: esa sigue siendo `VisitVitalSigns`, con una fila por
    visita, que jamas se sobreescribe (perder esa historia rompe la
    trazabilidad clinica que exige la NOM-024/NOM-004).

    IMPORTANTE: `no_exp` es compartido por todo el nucleo familiar
    (titular + derechohabientes); la clave efectiva de esta fila es
    SIEMPRE el par (`no_exp`, `pk_num`) -- ver `Meta.constraints`. Filtrar
    o hacer upsert usando solo `no_exp` mezcla el cache entre personas
    distintas de la misma familia.
    """

    id_latest = models.BigAutoField(primary_key=True, db_column="id_latest")
    # Plan identidad, Fase 5: el registro (afiliacion) atendido. Se resuelve
    # solo al guardar: consulta_medica.services.operational_link_service.
    patient = models.ForeignKey(
        "consulta_medica.Patient", db_column="id_paciente",
        on_delete=models.PROTECT, related_name="+",
    )
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, db_column="weight_kg")
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, db_column="height_cm")
    temperature_c = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        db_column="temperature_c",
        null=True,
        blank=True,
    )
    oxygen_saturation_pct = models.PositiveSmallIntegerField(
        db_column="oxygen_saturation_pct",
        null=True,
        blank=True,
    )
    heart_rate_bpm = models.PositiveSmallIntegerField(
        db_column="heart_rate_bpm",
        null=True,
        blank=True,
    )
    respiratory_rate_bpm = models.PositiveSmallIntegerField(
        db_column="respiratory_rate_bpm",
        null=True,
        blank=True,
    )
    blood_pressure_systolic = models.PositiveSmallIntegerField(
        db_column="blood_pressure_systolic",
        null=True,
        blank=True,
    )
    blood_pressure_diastolic = models.PositiveSmallIntegerField(
        db_column="blood_pressure_diastolic",
        null=True,
        blank=True,
    )
    waist_circumference_cm = models.PositiveSmallIntegerField(
        db_column="waist_circumference_cm",
        null=True,
        blank=True,
    )
    bmi = models.DecimalField(max_digits=6, decimal_places=2, db_column="bmi")
    glucosa_capilar_mgdl = models.PositiveSmallIntegerField(
        db_column="glucosa_capilar_mgdl",
        null=True,
        blank=True,
    )
    id_visit_origen = models.ForeignKey(
        "recepcion.Visit",
        db_column="id_visit_origen",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Visita de la que vino esta ultima captura (trazabilidad del cache).",
    )
    fch_modf = models.DateTimeField(auto_now=True, db_column="fch_modf")

    class Meta:
        db_table = "smt_patient_latest_vitals"
        constraints = [
            # Plan contraer la llave vieja: una fila por registro del paciente.
            models.UniqueConstraint(
                fields=["patient"], condition=models.Q(patient__isnull=False),
                name="smt_latest_vitals_paciente_uq",
            ),
        ]
