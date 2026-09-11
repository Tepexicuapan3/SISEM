from django.db import models

from apps.consulta_medica.storage import study_result_upload_to


class VisitConsultation(models.Model):
    id_consultation = models.BigAutoField(primary_key=True, db_column="id_consulta")
    id_visit = models.OneToOneField(
        "recepcion.Visit",
        db_column="id_visit",
        on_delete=models.CASCADE,
        related_name="consultation",
    )
    doctor = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="id_doctor",
        on_delete=models.PROTECT,
        related_name="consultas_atendidas",
    )
    primary_diagnosis = models.CharField(max_length=255, db_column="diagnostico_primario")
    cie = models.ForeignKey(
        "catalogos.CatCies",
        db_column="clave_cie",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="consultas",
    )
    final_note = models.TextField(db_column="nota_final")
    subjective = models.TextField(db_column="subjetivo", null=True, blank=True)
    objective = models.TextField(db_column="objetivo", null=True, blank=True)
    assessment = models.TextField(db_column="analisis", null=True, blank=True)
    plan = models.TextField(db_column="plan", null=True, blank=True)
    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)
    class Meta:
        db_table = "cns_visit_consultation"
        indexes = [
            models.Index(fields=["doctor"], name="cns_cons_doc_idx"),
            models.Index(fields=["is_active"], name="cns_cons_active_idx"),
            models.Index(fields=["created_at"], name="cns_cons_created_idx"),
        ]


class VisitConsultationRevision(models.Model):
    """
    Snapshot del valor de ``VisitConsultation`` justo ANTES de que se
    sobrescriba (ver ``ConsultationRepository.upsert_for_visit``).
    Versionado real requerido por NOM-024-SSA3-2012 -- reemplaza el
    anti-patron del legado de pisar el campo in-place sin dejar rastro del
    valor anterior.
    """

    consultation = models.ForeignKey(
        VisitConsultation,
        db_column="id_consulta",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    previous_primary_diagnosis = models.CharField(
        max_length=255, db_column="diagnostico_primario_anterior"
    )
    previous_cie = models.ForeignKey(
        "catalogos.CatCies",
        db_column="clave_cie_anterior",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    previous_final_note = models.TextField(db_column="nota_final_anterior")
    previous_subjective = models.TextField(
        db_column="subjetivo_anterior", null=True, blank=True
    )
    previous_objective = models.TextField(
        db_column="objetivo_anterior", null=True, blank=True
    )
    previous_assessment = models.TextField(
        db_column="analisis_anterior", null=True, blank=True
    )
    previous_plan = models.TextField(db_column="plan_anterior", null=True, blank=True)
    changed_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    changed_at = models.DateTimeField(db_column="fch_modf", auto_now_add=True)

    class Meta:
        db_table = "cns_visit_consultation_revision"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"Consulta {self.consultation_id} — revision {self.changed_at}"


class VisitDiagnosis(models.Model):
    """
    Diagnostico secundario/comorbilidad de una consulta -- complementa a
    VisitConsultation.primary_diagnosis/cie (que sigue siendo el
    diagnostico PRINCIPAL, obligatorio para cerrar la consulta segun
    NOM-024). Equivalente moderno de det_hisnotcie del legado, que permitia
    N codigos CIE-10 por nota en una tabla detalle. Baja logica (status)
    en vez de DELETE, mismo criterio que el legado (sw_status 'A'/'B').
    """

    class Status(models.TextChoices):
        ACTIVO = "activo", "Activo"
        CANCELADO = "cancelado", "Cancelado"

    id_visit_diagnosis = models.BigAutoField(
        primary_key=True, db_column="id_diagnostico",
    )
    consultation = models.ForeignKey(
        VisitConsultation,
        db_column="id_consulta",
        on_delete=models.PROTECT,
        related_name="secondary_diagnoses",
    )
    cie = models.ForeignKey(
        "catalogos.CatCies",
        db_column="clave_cie",
        on_delete=models.PROTECT,
        related_name="+",
    )
    notes = models.CharField(max_length=255, db_column="notas", null=True, blank=True)
    status = models.CharField(
        max_length=20, db_column="estatus", choices=Status.choices,
        default=Status.ACTIVO,
    )

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_visit_diagnosis"
        constraints = [
            models.UniqueConstraint(
                fields=["consultation", "cie"],
                condition=models.Q(status="activo"),
                name="cns_visit_diagnosis_one_active_per_cie",
            ),
        ]
        indexes = [
            models.Index(fields=["consultation"], name="cns_visitdiag_consult_idx"),
            models.Index(fields=["is_active"], name="cns_visitdiag_active_idx"),
        ]


class VisitPrescription(models.Model):
    id_prescription = models.BigAutoField(primary_key=True, db_column="id_receta")
    id_visit = models.OneToOneField(
        "recepcion.Visit",
        db_column="id_visit",
        on_delete=models.CASCADE,
        related_name="prescription",
    )
    items = models.JSONField(db_column="items")
    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_visit_prescription"
        indexes = [
            models.Index(fields=["is_active"], name="cns_rx_active_idx"),
            models.Index(fields=["created_at"], name="cns_rx_created_idx"),
        ]


class VisitPrescriptionItem(models.Model):
    """
    Item de receta estructurado y respaldado por catalogo -- complementa a
    VisitPrescription.items (JSON de texto libre, que se mantiene para
    indicaciones adicionales/generales). Equivalente moderno de
    det_receta del legado (medicamento + indicaciones + cantidad, tabla
    detalle 1:N contra la nota). Baja logica (status), no DELETE.
    """

    class Status(models.TextChoices):
        ACTIVO = "activo", "Activo"
        CANCELADO = "cancelado", "Cancelado"

    id_prescription_item = models.BigAutoField(
        primary_key=True, db_column="id_receta_item",
    )
    prescription = models.ForeignKey(
        "consulta_medica.VisitPrescription",
        db_column="id_receta",
        on_delete=models.PROTECT,
        related_name="structured_items",
    )
    medication = models.ForeignKey(
        "catalogos.Medicamentos",
        db_column="id_medic",
        on_delete=models.PROTECT,
        related_name="+",
    )
    dose = models.CharField(max_length=100, db_column="dosis", null=True, blank=True)
    indications = models.CharField(max_length=140, db_column="indicaciones")
    quantity = models.PositiveIntegerField(db_column="cantidad")
    status = models.CharField(
        max_length=20, db_column="estatus", choices=Status.choices,
        default=Status.ACTIVO,
    )

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_visit_prescription_item"
        constraints = [
            models.UniqueConstraint(
                fields=["prescription", "medication"],
                condition=models.Q(status="activo"),
                name="cns_rxitem_one_active_per_medication",
            ),
        ]
        indexes = [
            models.Index(fields=["prescription"], name="cns_rxitem_prescription_idx"),
            models.Index(fields=["is_active"], name="cns_rxitem_active_idx"),
        ]


class MedicalLeave(models.Model):
    """
    Incapacidad/licencia emitida a partir de una consulta cerrada. Solo el
    titular puede recibirla (pk_num == 0, validado en el use case, no aqui).
    A diferencia del legado (prefolio -> folio real via integracion con RH),
    SIRES no tiene esa integracion todavia: el folio se genera completo al
    crear, sin etapa intermedia. Ver medical_leave_usecase.py para las
    reglas de tope de dias y traslape.
    """

    id_medical_leave = models.BigAutoField(primary_key=True, db_column="id_licencia")
    consultation = models.ForeignKey(
        VisitConsultation,
        db_column="id_consulta",
        on_delete=models.PROTECT,
        related_name="medical_leaves",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    leave_type = models.ForeignKey(
        "catalogos.Licencias",
        db_column="id_tipo_licencia",
        on_delete=models.PROTECT,
        related_name="+",
    )
    is_subsequent = models.BooleanField(db_column="es_subsecuente", default=False)
    days = models.PositiveSmallIntegerField(db_column="dias")
    start_date = models.DateField(db_column="fecha_inicio")
    end_date = models.DateField(db_column="fecha_fin")
    folio = models.CharField(max_length=32, db_column="folio", unique=True)

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_medical_leave"
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="cns_medleave_patient_idx"),
            models.Index(fields=["is_active"], name="cns_medleave_active_idx"),
        ]


class StudyResult(models.Model):
    """
    Resultado de un estudio de laboratorio/gabinete, adjuntado como archivo.
    Conectado opcionalmente a `pases.ReferralStudyDetail` -- si el estudio
    vino de un pase/orden previo (Laboratorio/Gabinete), referral_study lo
    referencia (equivalente al legado pas_laboratorio/pas_gabinete ->
    ope_resultadoslab). Se mantiene nullable porque el medico puede seguir
    subiendo un resultado directo sin orden previa.
    """

    id_study_result = models.BigAutoField(primary_key=True, db_column="id_resultado")
    consultation = models.ForeignKey(
        VisitConsultation,
        db_column="id_consulta",
        on_delete=models.PROTECT,
        related_name="study_results",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    study_type = models.ForeignKey(
        "catalogos.EstudiosMed",
        db_column="id_estudio",
        on_delete=models.PROTECT,
        related_name="+",
    )
    referral_study = models.ForeignKey(
        "pases.ReferralStudyDetail",
        db_column="id_pase_estudio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="results",
    )
    result_date = models.DateField(db_column="fecha_resultado")
    notes = models.TextField(db_column="notas", null=True, blank=True)
    file = models.FileField(
        upload_to=study_result_upload_to, max_length=255,
    )

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_study_result"
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="cns_studyres_patient_idx"),
            models.Index(fields=["is_active"], name="cns_studyres_active_idx"),
        ]


class StomatologyHistory(models.Model):
    """
    Historia Clinica de Estomatologia: equivalente odontologico de
    ClinicalHistory, un solo registro por paciente/familiar (no_exp +
    pk_num). Replica los campos reales de `his_clinicad` documentados en
    investigacion_flujo.md SS17.3 -- NO incluye los signos vitales que esa
    tabla tambien guardaba en el legado, porque SIRES ya los resuelve bien
    con somatometria.VisitVitalSigns (una fila por visita, con fecha).
    """

    id_stomatology_history = models.BigAutoField(
        primary_key=True, db_column="id_historia_dental",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)

    # Antecedentes Heredofamiliares
    family_diabetes = models.BooleanField(db_column="af_diabetes", default=False)
    family_cancer = models.BooleanField(db_column="af_cancer", default=False)
    family_high_blood_pressure = models.BooleanField(db_column="af_presion_alta", default=False)
    family_low_blood_pressure = models.BooleanField(db_column="af_presion_baja", default=False)
    cause_of_death = models.CharField(max_length=255, db_column="causa_muerte", null=True, blank=True)

    # Antecedentes Personales Patologicos
    personal_diabetes = models.BooleanField(db_column="app_diabetes", default=False)
    personal_asthma = models.BooleanField(db_column="app_asma", default=False)
    personal_high_blood_pressure = models.BooleanField(db_column="app_presion_alta", default=False)
    personal_low_blood_pressure = models.BooleanField(db_column="app_presion_baja", default=False)
    personal_hepatitis = models.BooleanField(db_column="app_hepatitis", default=False)
    personal_hiv = models.BooleanField(db_column="app_vih", default=False)
    personal_smoking = models.BooleanField(db_column="app_tabaquismo", default=False)
    personal_alcoholism = models.BooleanField(db_column="app_alcoholismo", default=False)
    personal_substance_abuse = models.BooleanField(db_column="app_toxicomanias", default=False)

    # Antecedentes Personales No Patologicos
    habits = models.TextField(db_column="habitos", null=True, blank=True)
    diet = models.TextField(db_column="alimentacion", null=True, blank=True)

    # Antecedentes Quirurgicos / Traumaticos
    surgical_history = models.TextField(db_column="antecedentes_quirurgicos", null=True, blank=True)
    traumatic_history = models.TextField(db_column="antecedentes_traumaticos", null=True, blank=True)

    # Antecedentes Alergicos
    allergy_medications = models.TextField(db_column="alergia_medicamentos", null=True, blank=True)
    allergy_dental_material = models.TextField(db_column="alergia_material_dental", null=True, blank=True)
    allergy_anesthesia = models.TextField(db_column="alergia_anestesia", null=True, blank=True)
    allergy_food = models.TextField(db_column="alergia_alimentos", null=True, blank=True)
    allergy_environment = models.TextField(db_column="alergia_medio_ambiente", null=True, blank=True)
    allergy_other = models.TextField(db_column="alergia_otros", null=True, blank=True)

    # Padecimiento actual
    current_illness_history = models.TextField(db_column="padecimiento_actual", null=True, blank=True)

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_stomatology_history"
        constraints = [
            models.UniqueConstraint(fields=["no_exp", "pk_num"], name="cns_stomhist_patient_uniq"),
        ]
        indexes = [
            models.Index(fields=["is_active"], name="cns_stomhist_active_idx"),
        ]


class OdontogramTooth(models.Model):
    """
    Condicion de UNA pieza dental de un paciente/familiar, identificada por
    su numero FDI (ISO 3950): permanentes 11-48, deciduas (dientes de
    leche) 51-85. Un registro por (no_exp, pk_num, tooth_fdi) -- se
    sobreescribe al actualizar, no se versiona (decision explicita: mismo
    criterio que ClinicalHistory/StomatologyHistory). Un diente sin
    registro se interpreta como "sano" (ver OdontogramRepository).
    """

    class Condition(models.TextChoices):
        HEALTHY = "healthy", "Sano"
        CARIES = "caries", "Caries"
        FILLED = "filled", "Obturado"
        CROWN = "crown", "Corona"
        MISSING = "missing", "Ausente"
        EXTRACTION_NEEDED = "extraction_needed", "Extracción Indicada"
        ROOT_CANAL = "root_canal", "Endodoncia"
        SEALANT = "sealant", "Sellante"
        FRACTURE = "fracture", "Fracturado"
        IMPLANT = "implant", "Implante"

    id_odontogram_tooth = models.BigAutoField(primary_key=True, db_column="id_diente")
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    tooth_fdi = models.CharField(max_length=2, db_column="pieza_fdi")
    condition = models.CharField(
        max_length=32,
        db_column="condicion",
        choices=Condition.choices,
        default=Condition.HEALTHY,
    )
    notes = models.CharField(max_length=255, db_column="notas", null=True, blank=True)

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_odontogram_tooth"
        constraints = [
            models.UniqueConstraint(
                fields=["no_exp", "pk_num", "tooth_fdi"],
                name="cns_odontogram_tooth_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="cns_odontogram_patient_idx"),
        ]


class ClinicalHistory(models.Model):
    """
    Historia Clinica General: un solo registro por paciente/familiar
    (no_exp + pk_num), no versionado por consulta -- a diferencia de
    VisitConsultation. Se captura de forma incremental a lo largo de
    varias visitas, por eso todos los campos son nullable.
    """

    id_clinical_history = models.BigAutoField(primary_key=True, db_column="id_historia")
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)

    occupation = models.ForeignKey(
        "catalogos.Ocupaciones", db_column="id_ocupacion",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    education_level = models.ForeignKey(
        "catalogos.Escolaridad", db_column="id_escolaridad",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    marital_status = models.ForeignKey(
        "catalogos.EdoCivil", db_column="id_edocivil",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    religion = models.ForeignKey(
        "catalogos.Religion", db_column="id_religion",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    residence_type = models.ForeignKey(
        "catalogos.TipoResidencia", db_column="id_residencia",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    phone = models.CharField(max_length=15, db_column="telefono", null=True, blank=True)

    family_history = models.TextField(db_column="antecedentes", null=True, blank=True)
    current_illness = models.TextField(db_column="padecimiento_actual", null=True, blank=True)
    systems_review = models.TextField(db_column="organos_aparatos_sistemas", null=True, blank=True)
    head_exam = models.TextField(db_column="exploracion_cabeza", null=True, blank=True)
    neck_exam = models.TextField(db_column="exploracion_cuello", null=True, blank=True)
    chest_exam = models.TextField(db_column="exploracion_torax", null=True, blank=True)
    abdomen_exam = models.TextField(db_column="exploracion_abdomen", null=True, blank=True)
    genitals_exam = models.TextField(db_column="exploracion_genitales", null=True, blank=True)
    limbs_exam = models.TextField(db_column="exploracion_miembros", null=True, blank=True)
    diagnostic_management = models.TextField(db_column="manejo_diagnostico", null=True, blank=True)
    therapeutic_management = models.TextField(db_column="manejo_terapeutico", null=True, blank=True)
    allergies = models.TextField(db_column="alergias", null=True, blank=True)

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_clinical_history"
        constraints = [
            models.UniqueConstraint(fields=["no_exp", "pk_num"], name="cns_clinhist_patient_uniq"),
        ]
        indexes = [
            models.Index(fields=["is_active"], name="cns_clinhist_active_idx"),
        ]
