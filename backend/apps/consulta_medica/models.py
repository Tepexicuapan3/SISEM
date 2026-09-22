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


class ConsultationAddendum(models.Model):
    """
    Nota de aclaracion sobre una consulta YA CERRADA -- reemplaza el
    anti-patron del legado (``his_notas.sw_complemento``, un solo campo
    que se SOBRESCRIBE con cada adenda, perdiendo la anterior). Requisito
    real de NOM-004/024: un registro clinico firmado no se modifica, se
    aclara con una anotacion nueva, fechada y con autor, que queda junto a
    la original -- nunca la reemplaza ni la borra.

    Por diseno es append-only: no tiene ``update``/``delete`` en el
    repository, ni ``deleted_at``/``is_active`` -- una vez creada, una
    adenda es un hecho historico inmutable (si el medico se equivoco en la
    adenda misma, la correccion es OTRA adenda nueva, no editar esta).
    """

    id_addendum = models.BigAutoField(primary_key=True, db_column="id_adenda")
    consultation = models.ForeignKey(
        VisitConsultation,
        db_column="id_consulta",
        on_delete=models.PROTECT,
        related_name="addenda",
    )
    text = models.TextField(db_column="texto")
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)

    class Meta:
        db_table = "cns_consultation_addendum"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Consulta {self.consultation_id} — adenda {self.created_at}"


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

    # sdd/dispensacion-farmacia: estado de dispensacion en farmacia,
    # modificable UNICAMENTE por prescription_dispensation_usecase.dispense.
    # Permite eventos parciales (pendiente -> parcial -> dispensado) --
    # dispensed_quantity nunca puede superar quantity (CheckConstraint abajo,
    # ultima linea de defensa contra doble dispensacion -- ver design (c)).
    class DispensationStatus(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PARCIAL = "parcial", "Parcial"
        DISPENSADO = "dispensado", "Dispensado"

    dispensed_quantity = models.PositiveIntegerField(
        db_column="cantidad_dispensada", default=0,
    )
    dispensation_status = models.CharField(
        max_length=20, db_column="estatus_dispensacion",
        choices=DispensationStatus.choices, default=DispensationStatus.PENDIENTE,
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
            models.CheckConstraint(
                condition=models.Q(dispensed_quantity__lte=models.F("quantity")),
                name="cns_rxitem_dispensed_lte_quantity",
            ),
        ]
        indexes = [
            models.Index(fields=["prescription"], name="cns_rxitem_prescription_idx"),
            models.Index(fields=["is_active"], name="cns_rxitem_active_idx"),
        ]


class PrescriptionAuthorization(models.Model):
    """
    Solicitud de autorizacion de una receta que contiene medicamentos
    ESPECIAL o controlados -- equivalente moderno de `ope_autorizacion`
    del legado. Se crea automaticamente al agregar un item de receta que
    lo requiera (ver `prescription_item_usecase.add_prescription_item`);
    si todos los medicamentos son BASICO y no controlados, no se crea
    ninguna.

    A diferencia del legado (`det_clinicas.pw_autoriza`, que en la
    practica era reingresar la propia contraseña de login -- ver
    exploracion `sdd/autorizadores/*`), el autorizador se resuelve por
    RBAC real (permiso `clinico:recetas:authorize`), no por una clave
    compartida.

    Historico 1:N por receta (no OneToOne): el legado permitia mas de una
    solicitud de autorizacion por receta a lo largo del tiempo (PK
    compuesta con `no_autoriza` autoincremental en `ope_autorizacion`) --
    si ya hay una PENDIENTE no se crea otra, pero una ya
    autorizada/rechazada no se toca ni se revierte automaticamente.
    """

    class Status(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        AUTORIZADA = "autorizada", "Autorizada"
        RECHAZADA = "rechazada", "Rechazada"

    id_authorization = models.BigAutoField(primary_key=True, db_column="id_autorizacion")
    prescription = models.ForeignKey(
        VisitPrescription,
        db_column="id_receta",
        on_delete=models.PROTECT,
        related_name="authorizations",
    )
    # Denormalizado a proposito (mismo criterio que Visit.no_exp/pk_num en
    # todo SIRES): evita tener que navegar prescription.id_visit para
    # armar el contrato -- VisitPrescription.items (JSONField) tiene un
    # conflicto real psycopg2/Django al leerse fresco desde Postgres
    # (JSONB ya viene deserializado por el driver, Django intenta
    # re-parsearlo como string), asi que mejor no tocar ese modelo desde
    # una ruta de solo lectura que no lo necesita.
    visit = models.ForeignKey(
        "recepcion.Visit",
        db_column="id_visit",
        on_delete=models.PROTECT,
        related_name="prescription_authorizations",
    )
    # Denormalizado (mismo motivo que `visit` arriba): quien prescribio,
    # tomado de VisitPrescription.created_by_id en el momento de crear la
    # solicitud. Habilita la segregacion de funciones -- ver
    # `_ensure_not_self_authorization` en prescription_item_usecase --
    # sin tener que volver a tocar VisitPrescription despues.
    prescribed_by_id = models.BigIntegerField(db_column="usr_prescribe", null=True, blank=True)
    # Snapshot de conteos al momento de crear la solicitud (mismo criterio
    # que ope_autorizacion.no_medicamentos/no_especializado/no_controlado).
    medications_count = models.PositiveIntegerField(db_column="no_medicamentos", default=0)
    specialized_count = models.PositiveIntegerField(db_column="no_especializado", default=0)
    controlled_count = models.PositiveIntegerField(db_column="no_controlado", default=0)

    status = models.CharField(
        max_length=20, db_column="estatus", choices=Status.choices,
        default=Status.PENDIENTE,
    )
    authorized_by_id = models.BigIntegerField(db_column="usr_autoriza", null=True, blank=True)
    authorized_at = models.DateTimeField(db_column="fch_autoriza", null=True, blank=True)
    rejection_reason = models.CharField(
        max_length=500, db_column="motivo_rechazo", null=True, blank=True,
    )

    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)

    class Meta:
        db_table = "cns_prescription_authorization"
        indexes = [
            models.Index(fields=["status"], name="cns_rxauth_status_idx"),
            models.Index(fields=["prescription"], name="cns_rxauth_prescription_idx"),
        ]

    def __str__(self) -> str:
        return f"Autorizacion receta {self.prescription_id} — {self.status}"


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
    (no_exp + pk_num) -- no hay una fila nueva por cada consulta, a
    diferencia de VisitConsultation. Se captura de forma incremental a lo
    largo de varias visitas, por eso todos los campos son nullable.

    Las EDICIONES si quedan versionadas (ver ClinicalHistoryRevision mas
    abajo): cada vez que se sobrescribe un campo se guarda antes un
    snapshot del valor anterior, mismo patron que
    VisitConsultation/VisitConsultationRevision -- requerido por
    NOM-024-SSA3 (integridad del dato clinico sin riesgo de alteracion
    silenciosa).
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
    # max_length=50 para alojar el formato compuesto real del legado
    # ("cel XX-XXXX-XXXX tel XXXX-XXXX ext XXXXX", hasta 40 chars, con
    # margen) -- confirmado contra his_clinica.ds_telefono (varchar(50)).
    phone = models.CharField(max_length=50, db_column="telefono", null=True, blank=True)

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


class ClinicalHistoryRevision(models.Model):
    """
    Snapshot del valor de ``ClinicalHistory`` justo ANTES de que se
    sobrescriba (ver ``ClinicalHistoryRepository.update``). Mismo patron
    que ``VisitConsultationRevision`` -- versionado real requerido por
    NOM-024-SSA3, reemplaza el anti-patron del legado de pisar el campo
    in-place sin dejar rastro del valor anterior.
    """

    history = models.ForeignKey(
        ClinicalHistory,
        db_column="id_historia",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    previous_occupation = models.ForeignKey(
        "catalogos.Ocupaciones", db_column="id_ocupacion_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_education_level = models.ForeignKey(
        "catalogos.Escolaridad", db_column="id_escolaridad_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_marital_status = models.ForeignKey(
        "catalogos.EdoCivil", db_column="id_edocivil_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_religion = models.ForeignKey(
        "catalogos.Religion", db_column="id_religion_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_residence_type = models.ForeignKey(
        "catalogos.TipoResidencia", db_column="id_residencia_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_phone = models.CharField(
        max_length=50, db_column="telefono_anterior", null=True, blank=True
    )
    previous_family_history = models.TextField(db_column="antecedentes_anterior", null=True, blank=True)
    previous_current_illness = models.TextField(db_column="padecimiento_actual_anterior", null=True, blank=True)
    previous_systems_review = models.TextField(db_column="organos_aparatos_sistemas_anterior", null=True, blank=True)
    previous_head_exam = models.TextField(db_column="exploracion_cabeza_anterior", null=True, blank=True)
    previous_neck_exam = models.TextField(db_column="exploracion_cuello_anterior", null=True, blank=True)
    previous_chest_exam = models.TextField(db_column="exploracion_torax_anterior", null=True, blank=True)
    previous_abdomen_exam = models.TextField(db_column="exploracion_abdomen_anterior", null=True, blank=True)
    previous_genitals_exam = models.TextField(db_column="exploracion_genitales_anterior", null=True, blank=True)
    previous_limbs_exam = models.TextField(db_column="exploracion_miembros_anterior", null=True, blank=True)
    previous_diagnostic_management = models.TextField(db_column="manejo_diagnostico_anterior", null=True, blank=True)
    previous_therapeutic_management = models.TextField(db_column="manejo_terapeutico_anterior", null=True, blank=True)
    previous_allergies = models.TextField(db_column="alergias_anterior", null=True, blank=True)
    changed_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    changed_at = models.DateTimeField(db_column="fch_modf", auto_now_add=True)

    class Meta:
        db_table = "cns_clinical_history_revision"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"Historia {self.history_id} — revision {self.changed_at}"


class LegacyConsultationRecord(models.Model):
    """
    Archivo de SOLO LECTURA de las consultas del legado (`his_notas`,
    migradas desde MySQL -- ver
    `management/commands/migrar_notas_clinicas_legacy.py`). NO participa
    del flujo operativo vivo: a diferencia de `VisitConsultation`, no esta
    enlazada a `recepcion.Visit` a proposito, para no contaminar reportes/
    colas/turnos de hoy con 600k+ filas historicas sinteticas. Es
    consultable desde el expediente del paciente (seccion "Historial
    previo a SIRES") pero nunca se edita ni se borra -- es un volcado
    historico inmutable, igual espiritu que `ConsultationAddendum`.

    Los vitales de la nota (peso/talla/TA/pulso/temp/IMC/glucosa) se
    guardan tal cual vienen del legado (texto, sin normalizar) en vez de
    volcarse a `somatometria.VisitVitalSigns`: son un snapshot historico
    de ESA nota puntual, no signos vitales vigentes del paciente.

    `addendum_legacy` preserva `his_notas.sw_complemento` tal cual --
    ADVERTENCIA: el legado sobreescribia este campo sin versionar (mismo
    antipatron que motivo `ConsultationAddendum`), asi que si una nota
    tuvo mas de una adenda en el legado, solo sobrevive la ultima; la
    perdida ya ocurrio en el propio legado, no se puede recuperar en la
    migracion.
    """

    id_legacy_record = models.BigAutoField(primary_key=True, db_column="id_registro")
    legacy_folio = models.CharField(
        max_length=20, unique=True, db_column="folio_legado",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)

    consultation_date = models.DateField(db_column="fecha_consulta")
    consultation_time = models.CharField(
        max_length=10, db_column="hora_consulta", null=True, blank=True,
    )
    doctor_code_legacy = models.CharField(
        max_length=10, db_column="clave_medico_legado", null=True, blank=True,
    )
    clinic_code_legacy = models.IntegerField(
        db_column="clave_clinica_legado", null=True, blank=True,
    )

    subjective = models.TextField(db_column="subjetivo", null=True, blank=True)
    objective = models.TextField(db_column="objetivo", null=True, blank=True)
    assessment = models.TextField(db_column="analisis", null=True, blank=True)
    plan = models.TextField(db_column="plan", null=True, blank=True)
    diagnostic_impression = models.TextField(
        db_column="impresion_diagnostica", null=True, blank=True,
    )
    primary_cie_code_legacy = models.IntegerField(
        db_column="clave_cie_principal_legado", null=True, blank=True,
    )
    addendum_legacy = models.TextField(db_column="adenda_legado", null=True, blank=True)

    weight_legacy = models.CharField(max_length=8, db_column="peso_legado", null=True, blank=True)
    height_legacy = models.CharField(max_length=8, db_column="talla_legado", null=True, blank=True)
    blood_pressure_legacy = models.CharField(max_length=7, db_column="ta_legado", null=True, blank=True)
    pulse_legacy = models.CharField(max_length=20, db_column="pulso_legado", null=True, blank=True)
    temperature_legacy = models.CharField(max_length=10, db_column="temperatura_legado", null=True, blank=True)
    respiration_legacy = models.CharField(max_length=20, db_column="respiracion_legado", null=True, blank=True)
    bmi_legacy = models.CharField(max_length=8, db_column="imc_legado", null=True, blank=True)
    glucose_legacy = models.CharField(max_length=10, db_column="glucosa_legado", null=True, blank=True)

    is_first_visit_legacy = models.BooleanField(db_column="es_primera_vez_legado", null=True, blank=True)
    status_legacy = models.CharField(max_length=1, db_column="estatus_legado", null=True, blank=True)

    migrated_at = models.DateTimeField(db_column="fch_migracion", auto_now_add=True)

    class Meta:
        db_table = "cns_legacy_consultation_record"
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="cns_legacy_cons_noexp_pk_idx"),
            models.Index(fields=["consultation_date"], name="cns_legacy_cons_date_idx"),
        ]
        ordering = ["-consultation_date"]

    def __str__(self) -> str:
        return f"[Legado] {self.legacy_folio} — {self.no_exp}/{self.pk_num} ({self.consultation_date})"


class LegacyConsultationDiagnosis(models.Model):
    """
    Diagnostico CIE-10 de una nota del legado (`det_hisnotcie`, 1:N por
    `LegacyConsultationRecord`) -- archivo de SOLO LECTURA, mismo espiritu
    que `LegacyConsultationRecord` (ver su docstring). Es lo que le falta
    a `LegacyConsultationRecord.diagnostic_impression` (texto libre) para
    tener el diagnostico CODIFICADO, no solo texto.

    `record` es nullable a proposito: `det_hisnotcie.cd_snota` no tiene
    garantia de integridad referencial real contra `his_notas.cd_snota`
    en el legado (era una relacion logica, no un FK fisico) -- si algun
    diagnostico legado quedo huerfano (su nota no esta en el dump, o
    nunca existio), se preserva igual con `legacy_folio` crudo en vez de
    descartarlo silenciosamente.

    `legacy_id` (= `det_hisnotcie.cd_detcie`, PK real del legado) es la
    clave de upsert -- permite re-correr la migracion sin duplicar.
    """

    id_legacy_diagnosis = models.BigAutoField(primary_key=True, db_column="id_diagnostico_legado")
    legacy_id = models.BigIntegerField(unique=True, db_column="id_legado")
    record = models.ForeignKey(
        LegacyConsultationRecord,
        db_column="id_registro",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="legacy_diagnoses",
    )
    legacy_folio = models.CharField(max_length=20, db_column="folio_legado", db_index=True)
    cie_code_legacy = models.IntegerField(db_column="clave_cie_legado")
    doctor_code_legacy = models.CharField(
        max_length=10, db_column="clave_medico_legado", null=True, blank=True,
    )
    clinic_code_legacy = models.IntegerField(
        db_column="clave_clinica_legado", null=True, blank=True,
    )
    status_legacy = models.CharField(max_length=2, db_column="estatus_legado", null=True, blank=True)
    migrated_at = models.DateTimeField(db_column="fch_migracion", auto_now_add=True)

    class Meta:
        db_table = "cns_legacy_consultation_diagnosis"
        indexes = [
            models.Index(fields=["legacy_folio"], name="cns_legacy_diag_folio_idx"),
            models.Index(fields=["cie_code_legacy"], name="cns_legacy_diag_cie_idx"),
        ]

    def __str__(self) -> str:
        return f"[Legado] {self.legacy_folio} — CIE {self.cie_code_legacy}"
