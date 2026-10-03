import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone

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
    # his_notas ampliada (documento "Historia Clinica Unificada", 5.2): lo
    # que antes se sobrescribia en la historia ahora se captura por consulta.
    current_illness = models.TextField(db_column="ds_padecimiento", null=True, blank=True)
    systems_review = models.TextField(db_column="ds_aparatos_sistemas", null=True, blank=True)
    diagnostic_plan = models.TextField(db_column="ds_plan_diagnostico", null=True, blank=True)
    therapeutic_plan = models.TextField(db_column="ds_plan_terapeutico", null=True, blank=True)
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
    previous_current_illness = models.TextField(db_column="ds_padecimiento_anterior", null=True, blank=True)
    previous_systems_review = models.TextField(db_column="ds_aparatos_sistemas_anterior", null=True, blank=True)
    previous_diagnostic_plan = models.TextField(db_column="ds_plan_diagnostico_anterior", null=True, blank=True)
    previous_therapeutic_plan = models.TextField(db_column="ds_plan_terapeutico_anterior", null=True, blank=True)
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
    HC_ESTOMATOLOGIA (historia clinica unificada): seccion dental de la
    historia del paciente, un registro por paciente/familiar (no_exp +
    pk_num). Solo guarda lo PROPIO de estomatologia (higiene oral, tejidos
    blandos, ATM). Lo general -- antecedentes, habitos, alergias -- vive en
    las tablas permanentes compartidas por todas las especialidades
    (PersonalHistory, FamilyHistory, SurgicalHistory, Habit, Allergy); las
    casillas y textos que esta tabla guardaba antes se migraron ahi
    (migracion 0029). El odontograma versionado vive en Odontogram.

    Las EDICIONES quedan versionadas en StomatologyHistoryRevision.
    """

    class OralHygiene(models.TextChoices):
        GOOD = "good", "Buena"
        REGULAR = "regular", "Regular"
        POOR = "poor", "Mala"

    id_stomatology_history = models.BigAutoField(
        primary_key=True, db_column="id_historia_dental",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    # HISTORIA_CLINICA ||--o| HC_ESTOMATOLOGIA (documento 5.3).
    clinical_history = models.OneToOneField(
        "ClinicalHistory", db_column="id_historia", on_delete=models.PROTECT,
        related_name="stomatology_section",
    )

    oral_hygiene = models.CharField(
        max_length=10, db_column="higiene_oral", null=True, blank=True, choices=OralHygiene.choices,
    )
    brushings_per_day = models.PositiveSmallIntegerField(db_column="no_cepillados_dia", null=True, blank=True)
    uses_floss = models.BooleanField(db_column="sw_hilo_dental", null=True, blank=True)
    soft_tissues = models.TextField(db_column="tejidos_blandos", null=True, blank=True)
    tmj = models.TextField(db_column="atm", null=True, blank=True)

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


class StomatologyHistoryRevision(models.Model):
    """
    Snapshot del valor de ``StomatologyHistory`` justo ANTES de que se
    sobrescriba (ver ``StomatologyHistoryRepository.update``). Mismo patron
    que ``ClinicalHistoryRevision`` (NOM-024: nada se pisa sin rastro). Las
    versiones de los campos que se movieron a tablas permanentes quedaron
    como HistoricalNote origen "revision" (migracion 0029).
    """

    history = models.ForeignKey(
        StomatologyHistory,
        db_column="id_historia_dental",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    previous_oral_hygiene = models.CharField(
        max_length=10, db_column="higiene_oral_anterior", null=True, blank=True,
    )
    previous_brushings_per_day = models.PositiveSmallIntegerField(
        db_column="no_cepillados_dia_anterior", null=True, blank=True,
    )
    previous_uses_floss = models.BooleanField(db_column="sw_hilo_dental_anterior", null=True, blank=True)
    previous_soft_tissues = models.TextField(db_column="tejidos_blandos_anterior", null=True, blank=True)
    previous_tmj = models.TextField(db_column="atm_anterior", null=True, blank=True)
    changed_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    changed_at = models.DateTimeField(db_column="fch_modf", auto_now_add=True)

    class Meta:
        db_table = "cns_stomatology_history_revision"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"Historia dental {self.history_id} — revision {self.changed_at}"


class Allergy(models.Model):
    """
    Alergia estructurada de un paciente/familiar (no_exp + pk_num) --
    reemplaza el texto libre duplicado de ``ClinicalHistory.allergies`` y
    los 6 campos ``StomatologyHistory.allergy_*`` (change
    `alergias-unificadas`): una sola fuente de verdad, visible tanto en
    Medicina General como en Estomatologia, con severidad y (cuando aplica)
    ligada a un medicamento real del catalogo para poder cruzarla contra
    recetas (ver `prescription_item_usecase.add_prescription_item`).

    1:N por paciente (a diferencia de ClinicalHistory/StomatologyHistory) --
    puede haber varias alergias. Nunca se borra, solo se desactiva
    (`is_active=False`, mismo criterio "sin eliminaciones" de NOM-024).
    """

    class Severity(models.TextChoices):
        # Documento: L leve, M moderada, G grave.
        MILD = "L", "Leve"
        MODERATE = "M", "Moderada"
        SEVERE = "G", "Grave"

    class Source(models.TextChoices):
        # Nombre de contrato de la API (el frontend manda/recibe esto); en BD
        # se guarda como cd_servicio_origen (ver ServiceOrigin).
        GENERAL = "general", "Medicina General"
        STOMATOLOGY = "stomatology", "Estomatologia"

    class ServiceOrigin(models.IntegerChoices):
        # cat_servicios del legado (confirmado en el dump): 1, 5.
        GENERAL = 1, "Medicina General"
        STOMATOLOGY = 5, "Odontologia"

    SERVICE_BY_SOURCE = {"general": 1, "stomatology": 5}
    SOURCE_BY_SERVICE = {1: "general", 5: "stomatology"}

    id_allergy = models.BigAutoField(primary_key=True, db_column="id_alergia")
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)

    # ALERGIA.cd_tipo_alergia -> CAT_TIPO_ALERGIA (documento).
    allergy_type = models.ForeignKey(
        "catalogos.CatTipoAlergia", db_column="cd_tipo_alergia", on_delete=models.PROTECT,
        related_name="+",
    )
    substance = models.CharField(max_length=255, db_column="sustancia")
    # FK opcional al catalogo real -- solo tiene sentido para
    # category=MEDICATION. Permite el cruce receta<->alergia sin depender
    # de que `substance` coincida textualmente con el nombre del catalogo.
    medication = models.ForeignKey(
        "catalogos.Medicamentos",
        db_column="id_medic",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    severity = models.CharField(
        max_length=1, db_column="severidad", choices=Severity.choices,
    )
    reaction = models.TextField(db_column="reaccion", null=True, blank=True)
    # ALERGIA.cd_servicio_origen (documento): cat_servicios del legado,
    # 1 = Medicina General, 5 = Odontologia (confirmado en el dump). Solo
    # trazabilidad: la alergia es visible para todas las especialidades.
    service_origin_code = models.PositiveSmallIntegerField(
        db_column="cd_servicio_origen", choices=ServiceOrigin.choices,
    )

    @property
    def source(self):
        return self.SOURCE_BY_SERVICE.get(self.service_origin_code)

    class Status(models.TextChoices):
        # Documento: A activa, R resuelta, E capturada por error.
        ACTIVE = "A", "Activa"
        RESOLVED = "R", "Resuelta"
        ENTERED_IN_ERROR = "E", "Capturada por error"

    # Estado clinico (documento: A activa, R resuelta, E error). Cambiarlo
    # exige motivo (`status_reason`). `is_active=False` <=> ENTERED_IN_ERROR:
    # una alergia resuelta sigue siendo historia visible, no se oculta.
    status = models.CharField(
        max_length=1, db_column="estado", choices=Status.choices, default=Status.ACTIVE,
    )
    status_reason = models.CharField(max_length=500, db_column="motivo_estado", null=True, blank=True)

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "cns_allergy"
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="cns_allergy_patient_idx"),
            # Documento: ix_alergia_paciente (no_exp, tp_paciente, estado).
            models.Index(fields=["no_exp", "pk_num", "status"], name="ix_alergia_paciente"),
            models.Index(fields=["is_active"], name="cns_allergy_active_idx"),
        ]

    def __str__(self) -> str:
        return f"Alergia {self.substance} ({self.no_exp}/{self.pk_num})"


class AllergyRevision(models.Model):
    """
    Snapshot del valor de ``Allergy`` justo ANTES de que se sobrescriba
    (ver ``AllergyRepository.update``). Mismo patron que
    ``ClinicalHistoryRevision`` -- versionado real requerido por NOM-024.
    Append-only, sin soft-delete (una alergia desactivada no se "revisiona",
    queda registrado en `Allergy.deleted_at`/`deleted_by_id` directamente).
    """

    allergy = models.ForeignKey(
        Allergy,
        db_column="id_alergia",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    previous_allergy_type = models.ForeignKey(
        "catalogos.CatTipoAlergia", db_column="cd_tipo_alergia_anterior", on_delete=models.PROTECT,
        related_name="+",
    )
    previous_substance = models.CharField(max_length=255, db_column="sustancia_anterior")
    previous_medication = models.ForeignKey(
        "catalogos.Medicamentos",
        db_column="id_medic_anterior",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    previous_severity = models.CharField(
        max_length=1, db_column="severidad_anterior", choices=Allergy.Severity.choices,
    )
    previous_reaction = models.TextField(db_column="reaccion_anterior", null=True, blank=True)
    changed_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    changed_at = models.DateTimeField(db_column="fch_modf", auto_now_add=True)

    class Meta:
        db_table = "cns_allergy_revision"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"Alergia {self.allergy_id} — revision {self.changed_at}"


class Sex(models.TextChoices):
    # Mismas letras que la posicion 11 del CURP (RENAPO), incluida X.
    MALE = "H", "Hombre"
    FEMALE = "M", "Mujer"
    NON_BINARY = "X", "No binario"


class Patient(models.Model):
    """
    PACIENTE (documento "Historia Clinica Unificada", 5.1 "SERMED como
    fuente, PACIENTE como tabla propia"): identidad estable del paciente a la
    que apuntan las tablas clinicas, aunque SERMED lo de de baja o lo borre.

    - Datos que manda SERMED (nombre, fecha de nacimiento, sexo y CURP de
      titulares): se copian de las replicas cat_empleados/cat_familiar en
      cada sincronizacion; no se capturan en SIRES.
    - Datos que captura SIRES: ocupacion, escolaridad, estado civil,
      religion, residencia, telefono y la CURP de familiares. Sus ediciones
      se versionan en PatientRevision (NOM-024).

    Identificadores del familiar: pk_num (PK_NUM de SERMED) y cd_familiar
    (cd_familiar de dbclinicas, el tp_paciente del legado). Hay familiares
    del legado sin PK_NUM: se identifican solo por cd_familiar.
    """

    class CurpSource(models.TextChoices):
        SERMED = "O", "Oracle (SERMED)"
        CAPTURED = "C", "Capturada en SIRES"

    id_patient = models.BigAutoField(primary_key=True, db_column="id_paciente")
    # Identificador para compartir con otras instituciones (NOM-024). Nunca cambia.
    uuid = models.UUIDField(db_column="uuid", default=uuid.uuid4, unique=True, editable=False)
    no_exp = models.CharField(max_length=20, db_column="no_exp")
    # 0 = titular. NULL = familiar sin PK_NUM en SERMED (solo cd_familiar).
    pk_num = models.IntegerField(db_column="pk_num", default=0, null=True, blank=True)
    legacy_family_code = models.IntegerField(db_column="cd_familiar", null=True, blank=True)

    # Copiados de SERMED (cat_empleados / cat_familiar). "RN" en ds_nombre
    # mientras un recien nacido no este registrado en Capital Humano.
    paternal_surname = models.CharField(max_length=100, db_column="ds_paterno", null=True, blank=True)
    maternal_surname = models.CharField(max_length=100, db_column="ds_materno", null=True, blank=True)
    first_name = models.CharField(max_length=100, db_column="ds_nombre", null=True, blank=True)
    birth_date = models.DateField(db_column="fe_nacimiento", null=True, blank=True)

    # Identidad (NOM-024). Todavia sin unique: SERMED tiene CURP repetidas
    # (una persona con varios NO_EXP) que se resuelven fusionando pacientes.
    # Ver el comando reporte_curp_duplicadas.
    curp = models.CharField(max_length=18, db_column="curp", null=True, blank=True, db_index=True)
    curp_source = models.CharField(
        max_length=1, db_column="curp_origen", choices=CurpSource.choices, null=True, blank=True,
    )
    sex = models.CharField(max_length=1, db_column="sexo", choices=Sex.choices, null=True, blank=True)

    occupation = models.ForeignKey(
        "catalogos.Ocupaciones", db_column="cd_ocupacion",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    education_level = models.ForeignKey(
        "catalogos.Escolaridad", db_column="cd_escolaridad",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    marital_status = models.ForeignKey(
        "catalogos.EdoCivil", db_column="cd_edocivil",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    religion = models.ForeignKey(
        "catalogos.Religion", db_column="cd_religion",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    residence_type = models.ForeignKey(
        "catalogos.TipoResidencia", db_column="cd_residencia",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    # 50: el legado guarda "cel ... tel ... ext ..." (his_clinica.ds_telefono).
    phone = models.CharField(max_length=50, db_column="ds_telefono", null=True, blank=True)

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)

    class Meta:
        db_table = "cns_paciente"
        constraints = [
            models.UniqueConstraint(
                fields=["no_exp", "pk_num"], condition=models.Q(pk_num__isnull=False),
                name="cns_paciente_exp_pknum_uq",
            ),
            models.UniqueConstraint(
                fields=["legacy_family_code"], condition=models.Q(legacy_family_code__isnull=False),
                name="cns_paciente_cd_familiar_uq",
            ),
            # Nadie queda sin identificador: titular (pk_num 0), familiar con
            # PK_NUM, o familiar del legado con solo cd_familiar.
            models.CheckConstraint(
                condition=models.Q(pk_num__isnull=False) | models.Q(legacy_family_code__isnull=False),
                name="cns_paciente_con_identificador",
            ),
        ]


class PatientRevision(models.Model):
    """Snapshot de ``Patient`` justo ANTES de sobrescribirse (NOM-024)."""

    patient = models.ForeignKey(
        Patient, db_column="id_paciente", on_delete=models.CASCADE, related_name="revisions",
    )
    previous_curp = models.CharField(max_length=18, db_column="curp_anterior", null=True, blank=True)
    previous_sex = models.CharField(max_length=1, db_column="sexo_anterior", null=True, blank=True)
    previous_occupation = models.ForeignKey(
        "catalogos.Ocupaciones", db_column="cd_ocupacion_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_education_level = models.ForeignKey(
        "catalogos.Escolaridad", db_column="cd_escolaridad_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_marital_status = models.ForeignKey(
        "catalogos.EdoCivil", db_column="cd_edocivil_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_religion = models.ForeignKey(
        "catalogos.Religion", db_column="cd_religion_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_residence_type = models.ForeignKey(
        "catalogos.TipoResidencia", db_column="cd_residencia_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_phone = models.CharField(max_length=50, db_column="ds_telefono_anterior", null=True, blank=True)
    changed_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    changed_at = models.DateTimeField(db_column="fch_modf", auto_now_add=True)

    class Meta:
        db_table = "cns_paciente_revision"
        ordering = ["changed_at"]


class ClinicalHistory(models.Model):
    """
    HISTORIA_CLINICA (documento "Historia Clinica Unificada", 5.1): cabecera
    UNICA por paciente (no_exp + tp_paciente/pk_num), 1:1 con PACIENTE.
    Guarda cuando, donde y quien la abrio. Los datos de la persona viven en
    Patient; los datos permanentes (alergias, antecedentes, habitos) en sus
    tablas 1:N; el texto del modelo anterior en HistoricalNote (1:N).
    """

    # Compatibilidad: el enum vive a nivel de modulo (lo usa Patient).
    Sex = Sex

    id_clinical_history = models.BigAutoField(primary_key=True, db_column="id_historia")
    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    patient = models.OneToOneField(
        Patient, db_column="id_paciente", on_delete=models.PROTECT, related_name="clinical_history",
    )
    opened_on = models.DateField(db_column="fe_apertura", default=timezone.localdate)
    # Del legado: his_clinica.cd_clinica / cd_medico.
    opening_clinic_code = models.IntegerField(db_column="cd_clinica_apertura", null=True, blank=True)
    opening_doctor_code = models.CharField(max_length=10, db_column="cd_medico_apertura", null=True, blank=True)

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


# ════════════════════════════════════════════════════════════════════════════
# Historia clinica unificada (documento "Historia Clinica Unificada" --
# propuesta de modelo de datos, 2026-09-25). Una historia por paciente con
# secciones por especialidad; cada dato en su dueno: la persona
# (ClinicalHistory = ficha), la historia permanente (antecedentes, habitos,
# alergias -- compartidos por todas las especialidades) o la consulta
# (exploracion fisica). Filas en lugar de columnas para listas que crecen.
# Nada se borra: baja logica con motivo + auditoria en AuditoriaEvento.
# ════════════════════════════════════════════════════════════════════════════


class SpecialtySource(models.TextChoices):
    """Especialidad que capturo el registro -- solo trazabilidad, NUNCA
    restringe la visibilidad (todo lo permanente se ve en todas)."""

    GENERAL = "general", "Medicina General"
    STOMATOLOGY = "stomatology", "Estomatologia"
    LEGACY = "legacy", "Migrado del sistema anterior"


class PatientRecordBase(models.Model):
    """Columnas comunes de los registros permanentes 1:N por paciente."""

    no_exp = models.CharField(max_length=20, db_column="no_exp")
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    source = models.CharField(
        max_length=20, db_column="origen", choices=SpecialtySource.choices,
        default=SpecialtySource.GENERAL,
    )
    # Referencia de origen para migraciones idempotentes
    # (ej. "his_clinicad:1234", "cns_stomatology_history:5").
    legacy_ref = models.CharField(max_length=60, db_column="ref_origen", null=True, blank=True, db_index=True)

    is_active = models.BooleanField(db_column="est_activo", default=True)
    deletion_reason = models.CharField(max_length=500, db_column="motivo_baja", null=True, blank=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        abstract = True


class PersonalHistory(PatientRecordBase):
    """ANTECEDENTE_PERSONAL: padecimientos propios del paciente (CIE-10)."""

    class Status(models.TextChoices):
        # Documento: A activo, R resuelto.
        ACTIVE = "A", "Activo"
        RESOLVED = "R", "Resuelto"

    id_personal_history = models.BigAutoField(primary_key=True, db_column="id_antecedente")
    cie = models.ForeignKey(
        "catalogos.CatCies", db_column="cie_codigo", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    description = models.CharField(max_length=500, db_column="descripcion", null=True, blank=True)
    diagnosis_date = models.DateField(db_column="fe_diagnostico", null=True, blank=True)
    status = models.CharField(
        max_length=1, db_column="estado", choices=Status.choices, default=Status.ACTIVE,
    )

    class Meta:
        db_table = "cns_antecedente_personal"
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_antpers_patient_idx")]


class FamilyHistory(PatientRecordBase):
    """ANTECEDENTE_FAMILIAR: heredofamiliares, con parentesco (NULL = no especificado)."""

    id_family_history = models.BigAutoField(primary_key=True, db_column="id_antecedente")
    relationship = models.ForeignKey(
        "catalogos.Parentesco", db_column="id_parentesco", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    cie = models.ForeignKey(
        "catalogos.CatCies", db_column="cie_codigo", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    description = models.CharField(max_length=500, db_column="descripcion", null=True, blank=True)
    is_deceased = models.BooleanField(db_column="sw_finado", default=False)
    cause_of_death = models.CharField(max_length=255, db_column="causa_muerte", null=True, blank=True)

    class Meta:
        db_table = "cns_antecedente_familiar"
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_antfam_patient_idx")]


class SurgicalHistory(PatientRecordBase):
    """ANTECEDENTE_QUIRURGICO: procedimientos previos (opcional CIE-9-MC)."""

    id_surgical_history = models.BigAutoField(primary_key=True, db_column="id_quirurgico")
    procedure = models.CharField(max_length=500, db_column="procedimiento")
    procedure_cie9 = models.ForeignKey(
        "catalogos.CatCie9Mc", db_column="id_cie9_mc", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    approximate_date = models.DateField(db_column="fe_aproximada", null=True, blank=True)
    place = models.CharField(max_length=255, db_column="lugar", null=True, blank=True)

    class Meta:
        db_table = "cns_antecedente_quirurgico"
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_antquir_patient_idx")]


class Habit(PatientRecordBase):
    """HABITO: tabaquismo, alcoholismo, toxicomanias, alimentacion..."""

    class Status(models.TextChoices):
        # Documento: A actual, E ex (ej. exfumador).
        CURRENT = "A", "Actual"
        FORMER = "E", "Ex (ya no lo practica)"

    id_habit = models.BigAutoField(primary_key=True, db_column="id_habito_paciente")
    habit = models.ForeignKey(
        "catalogos.CatHabito", db_column="id_habito", on_delete=models.PROTECT, related_name="+",
    )
    frequency = models.CharField(max_length=100, db_column="frecuencia", null=True, blank=True)
    quantity = models.CharField(max_length=100, db_column="cantidad", null=True, blank=True)
    since = models.DateField(db_column="desde", null=True, blank=True)
    status = models.CharField(
        max_length=1, db_column="estado", choices=Status.choices, default=Status.CURRENT,
    )
    notes = models.TextField(db_column="notas", null=True, blank=True)

    class Meta:
        db_table = "cns_habito"
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_habito_patient_idx")]


class HistoricalNote(models.Model):
    """
    NOTA_HISTORICA: texto del modelo anterior conservado de SOLO LECTURA.
    El texto acumulado del legado (`<texto> [dd/mm/aaaa (usuario)] - `) se
    parte en una nota por anotacion, recuperando fecha y autor. Nunca se
    edita ni se borra (no tiene endpoint de escritura).
    """

    class Section(models.TextChoices):
        BACKGROUND = "antecedentes", "Antecedentes"
        CURRENT_ILLNESS = "padecimiento", "Padecimiento actual"
        SYSTEMS_REVIEW = "aparatos_sistemas", "Interrogatorio por aparatos y sistemas"
        HEAD = "cabeza", "Exploracion: cabeza"
        NECK = "cuello", "Exploracion: cuello"
        CHEST = "torax", "Exploracion: torax"
        ABDOMEN = "abdomen", "Exploracion: abdomen"
        GENITALS = "genitales", "Exploracion: genitales"
        LIMBS = "miembros", "Exploracion: miembros"
        DIAGNOSTIC_MANAGEMENT = "manejo_diagnostico", "Manejo diagnostico"
        THERAPEUTIC_MANAGEMENT = "manejo_terapeutico", "Manejo terapeutico"
        ALLERGIES = "alergias", "Alergias (texto original)"
        HABITS = "habitos", "Habitos"
        SURGICAL = "quirurgicos", "Antecedentes quirurgicos"
        TRAUMATIC = "traumaticos", "Antecedentes traumaticos"
        VITAL_SIGNS = "signos_vitales", "Signos vitales"
        OTHER = "otro", "Otro"

    class Origin(models.TextChoices):
        # Documento: "M migrado". V = version anterior de la historia (tambien
        # migrada, se distingue para mostrarla como tal).
        LEGACY_TEXT = "M", "Migrado del sistema anterior"
        REVISION = "V", "Version anterior de la historia"

    id_historical_note = models.BigAutoField(primary_key=True, db_column="id_nota")
    # HISTORIA_CLINICA ||--o{ NOTA_HISTORICA (documento).
    clinical_history = models.ForeignKey(
        "ClinicalHistory", db_column="id_historia", on_delete=models.PROTECT,
        related_name="historical_notes",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp")
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    specialty = models.CharField(
        max_length=20, db_column="especialidad", choices=SpecialtySource.choices,
        default=SpecialtySource.GENERAL,
    )
    section = models.CharField(max_length=30, db_column="apartado", choices=Section.choices)
    noted_on = models.DateField(db_column="fe_anotacion", null=True, blank=True)
    author = models.CharField(max_length=100, db_column="usuario", null=True, blank=True)
    content = models.TextField(db_column="contenido")
    origin = models.CharField(
        max_length=1, db_column="origen", choices=Origin.choices, default=Origin.LEGACY_TEXT,
    )
    legacy_ref = models.CharField(max_length=60, db_column="ref_origen", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)

    class Meta:
        db_table = "cns_nota_historica"
        ordering = ["noted_on", "id_historical_note"]
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_notahist_patient_idx")]


class LegacyVitalSigns(models.Model):
    """
    SIGNOS_VITALES del modelo anterior: "sin consulta, fecha desconocida"
    (documento "Historia Clinica Unificada", seccion 7). Tabla propia y no
    `smt_visit_vitals` porque esa exige visita y peso/talla/IMC: el legado
    solo guardaba la ULTIMA medicion (se pisaba en cada edicion) como texto
    libre. Cada valor numerico queda NULL si no paso el rango de
    plausibilidad; `raw_text` conserva siempre lo capturado originalmente.
    Solo lectura: nunca alimenta el cache `smt_patient_latest_vitals`.
    """

    id_legacy_vitals = models.BigAutoField(primary_key=True, db_column="id_signos")
    clinical_history = models.ForeignKey(
        "ClinicalHistory", db_column="id_historia", on_delete=models.PROTECT,
        related_name="legacy_vital_signs",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp")
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    specialty = models.CharField(
        max_length=20, db_column="especialidad", choices=SpecialtySource.choices,
        default=SpecialtySource.GENERAL,
    )
    measured_on = models.DateField(db_column="fe_medicion", null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, db_column="no_peso", null=True, blank=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, db_column="no_talla", null=True, blank=True)
    blood_pressure_systolic = models.PositiveSmallIntegerField(db_column="no_ta_sistolica", null=True, blank=True)
    blood_pressure_diastolic = models.PositiveSmallIntegerField(db_column="no_ta_diastolica", null=True, blank=True)
    heart_rate_bpm = models.PositiveSmallIntegerField(db_column="no_pulso", null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, db_column="no_temp", null=True, blank=True)
    respiratory_rate_bpm = models.PositiveSmallIntegerField(db_column="no_resp", null=True, blank=True)
    bmi = models.DecimalField(max_digits=6, decimal_places=2, db_column="no_imc", null=True, blank=True)
    raw_text = models.TextField(db_column="ds_texto_original")
    legacy_ref = models.CharField(max_length=60, db_column="ref_origen", unique=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)

    class Meta:
        db_table = "cns_signos_vitales_legado"
        ordering = ["measured_on", "id_legacy_vitals"]
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_sv_legado_patient_idx")]


# ── Plan de migracion (documento "Historia Clinica Unificada", seccion 8) ─────

class LegacyMigrationRun(models.Model):
    """Bitacora de ejecucion: quien corrio que comando de migracion legacy,
    cuando, con que opciones y como termino (tambien los --dry-run)."""

    class Status(models.TextChoices):
        RUNNING = "E", "En curso"
        OK = "O", "Terminada"
        FAILED = "F", "Fallida"

    id_run = models.BigAutoField(primary_key=True, db_column="id_ejecucion")
    command = models.CharField(max_length=80, db_column="comando")
    operator = models.CharField(max_length=100, db_column="operador")
    host = models.CharField(max_length=100, db_column="equipo", null=True, blank=True)
    options = models.TextField(db_column="opciones", null=True, blank=True)
    dry_run = models.BooleanField(db_column="sw_simulacion", default=False)
    status = models.CharField(max_length=1, db_column="estatus", choices=Status.choices, default=Status.RUNNING)
    rows_read = models.IntegerField(db_column="filas_leidas", null=True, blank=True)
    summary = models.TextField(db_column="resumen", null=True, blank=True)
    started_at = models.DateTimeField(db_column="fch_inicio", auto_now_add=True)
    finished_at = models.DateTimeField(db_column="fch_fin", null=True, blank=True)

    class Meta:
        db_table = "cns_bitacora_migracion"
        ordering = ["-started_at"]


class LegacyMigrationConflict(models.Model):
    """Dato de la ficha del paciente en el que dos fuentes no coinciden
    (his_clinica vs his_clinicad, o legado vs lo editado en SIRES). Queda el
    valor que gano y el que se descarto, para revision humana."""

    class Winner(models.TextChoices):
        LEGACY_NEWER = "L", "Legado mas reciente (se aplico)"
        PREVIOUS_LEGACY = "P", "Se conservo el legado previo (mas reciente o igual)"
        SIRES = "S", "Se conservo lo editado en SIRES"

    id_conflict = models.BigAutoField(primary_key=True, db_column="id_conflicto")
    run = models.ForeignKey(
        LegacyMigrationRun, db_column="id_ejecucion", on_delete=models.PROTECT,
        null=True, blank=True, related_name="conflicts",
    )
    no_exp = models.CharField(max_length=20, db_column="no_exp")
    pk_num = models.IntegerField(db_column="tp_paciente", default=0)
    field = models.CharField(max_length=40, db_column="campo")
    kept_value = models.CharField(max_length=255, db_column="valor_conservado", null=True, blank=True)
    discarded_value = models.CharField(max_length=255, db_column="valor_descartado", null=True, blank=True)
    legacy_ref = models.CharField(max_length=60, db_column="ref_origen")
    legacy_date = models.DateField(db_column="fe_origen", null=True, blank=True)
    winner = models.CharField(max_length=1, db_column="ganador", choices=Winner.choices)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)

    class Meta:
        db_table = "cns_conflicto_migracion"
        ordering = ["no_exp", "pk_num", "field"]
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_conflicto_patient_idx")]


class PatientLegacySource(models.Model):
    """De que fila del legado (y con que fecha) salio cada dato de la ficha.
    Hace que la regla "gana el fe_hisclin mas reciente" no dependa del orden
    en que se corran los comandos, y permite distinguir un valor que vino del
    legado de uno editado despues en SIRES (que nunca se pisa)."""

    id_source = models.BigAutoField(primary_key=True, db_column="id_origen")
    patient = models.ForeignKey(
        Patient, db_column="id_paciente", on_delete=models.CASCADE, related_name="legacy_sources",
    )
    field = models.CharField(max_length=40, db_column="campo")
    value = models.CharField(max_length=255, db_column="valor")
    legacy_ref = models.CharField(max_length=60, db_column="ref_origen")
    legacy_date = models.DateField(db_column="fe_origen", null=True, blank=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)

    class Meta:
        db_table = "cns_paciente_origen_legado"
        constraints = [
            models.UniqueConstraint(fields=["patient", "field"], name="cns_paciente_origen_campo_uq"),
        ]


class PhysicalExamFinding(models.Model):
    """
    EXPLORACION_FISICA por region y POR CONSULTA (antes 6 columnas de texto en
    la historia que se pisaban con cada edicion). Editable solo mientras la
    visita esta `en_consulta`; despues, aclaraciones via ConsultationAddendum.
    """

    id_finding = models.BigAutoField(primary_key=True, db_column="id_exploracion")
    consultation = models.ForeignKey(
        VisitConsultation, db_column="id_consulta", on_delete=models.CASCADE,
        related_name="physical_exam_findings",
    )
    region = models.ForeignKey(
        "catalogos.CatRegionCorporal", db_column="id_region", on_delete=models.PROTECT, related_name="+",
    )
    is_normal = models.BooleanField(db_column="sw_normal", default=True)
    finding = models.TextField(db_column="hallazgo", null=True, blank=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)

    class Meta:
        db_table = "cns_exploracion_fisica"
        constraints = [
            models.UniqueConstraint(fields=["consultation", "region"], name="cns_expfis_consulta_region_uniq"),
        ]


class Odontogram(models.Model):
    """
    ODONTOGRAMA versionado: cada consulta que modifica el estado dental genera
    una version nueva (copia de la anterior + cambios), en lugar de pisar el
    estado previo. El CPOD (cariados/perdidos/obturados) se recalcula al
    guardar cada pieza.
    """

    class Dentition(models.TextChoices):
        PERMANENT = "P", "Permanente"
        DECIDUOUS = "T", "Temporal"
        MIXED = "M", "Mixta"

    class Origin(models.TextChoices):
        CAPTURE = "capture", "Captura"
        MIGRATED = "migrated", "Migrado del odontograma anterior"

    id_odontogram = models.BigAutoField(primary_key=True, db_column="id_odontograma")
    no_exp = models.CharField(max_length=20, db_column="no_exp")
    pk_num = models.IntegerField(db_column="pk_num", default=0)
    # HC_ESTOMATOLOGIA ||--o{ ODONTOGRAMA (documento 5.3).
    stomatology_history = models.ForeignKey(
        StomatologyHistory, db_column="id_hc_estoma", on_delete=models.PROTECT,
        related_name="odontograms",
    )
    visit = models.ForeignKey(
        "recepcion.Visit", db_column="id_visit", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    dentition = models.CharField(
        max_length=1, db_column="tp_denticion", choices=Dentition.choices, default=Dentition.PERMANENT,
    )
    dmft_decayed = models.PositiveSmallIntegerField(db_column="cpod_cariados", default=0)
    dmft_missing = models.PositiveSmallIntegerField(db_column="cpod_perdidos", default=0)
    dmft_filled = models.PositiveSmallIntegerField(db_column="cpod_obturados", default=0)
    # ODONTOGRAMA.indice_cpod (documento): cariados + perdidos + obturados.
    dmft_total = models.DecimalField(
        max_digits=5, decimal_places=2, db_column="indice_cpod", default=0,
    )
    origin = models.CharField(
        max_length=10, db_column="origen", choices=Origin.choices, default=Origin.CAPTURE,
    )
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)

    class Meta:
        db_table = "cns_odontograma"
        ordering = ["-created_at", "-id_odontogram"]
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_odontograma_patient_idx")]

    @property
    def dmft_index(self):
        return int(self.dmft_total)


class OdontogramToothState(models.Model):
    """ODONTOGRAMA_PIEZA: estado de una pieza (o cara) en una version.
    `face` vacio = pieza completa; O/M/D/V/L = cara especifica."""

    class Face(models.TextChoices):
        WHOLE = "", "Pieza completa"
        OCCLUSAL = "O", "Oclusal"
        MESIAL = "M", "Mesial"
        DISTAL = "D", "Distal"
        VESTIBULAR = "V", "Vestibular"
        LINGUAL = "L", "Lingual/Palatina"

    id_tooth_state = models.BigAutoField(primary_key=True, db_column="id_pieza_estado")
    odontogram = models.ForeignKey(
        Odontogram, db_column="id_odontograma", on_delete=models.CASCADE, related_name="teeth",
    )
    tooth = models.ForeignKey(
        "catalogos.CatPiezaDental", db_column="pieza_fdi", on_delete=models.PROTECT, related_name="+",
    )
    face = models.CharField(max_length=1, db_column="cara", choices=Face.choices, default="", blank=True)
    state = models.ForeignKey(
        "catalogos.CatEstadoPieza", db_column="id_estado_pieza", on_delete=models.PROTECT, related_name="+",
    )
    observation = models.CharField(max_length=255, db_column="observacion", null=True, blank=True)

    class Meta:
        db_table = "cns_odontograma_pieza"
        constraints = [
            models.UniqueConstraint(fields=["odontogram", "tooth", "face"], name="cns_odontpieza_uniq"),
        ]


class DentalTreatment(PatientRecordBase):
    """TRATAMIENTO_DENTAL: procedimiento planeado/realizado sobre una pieza."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planeado"
        DONE = "done", "Realizado"

    id_dental_treatment = models.BigAutoField(primary_key=True, db_column="id_tratamiento")
    visit = models.ForeignKey(
        "recepcion.Visit", db_column="id_visit", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    tooth = models.ForeignKey(
        "catalogos.CatPiezaDental", db_column="pieza_fdi", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    procedure = models.CharField(max_length=500, db_column="procedimiento")
    procedure_cie9 = models.ForeignKey(
        "catalogos.CatCie9Mc", db_column="id_cie9_mc", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    status = models.CharField(
        max_length=10, db_column="estado", choices=Status.choices, default=Status.PLANNED,
    )
    performed_at = models.DateTimeField(db_column="fch_realizado", null=True, blank=True)

    class Meta:
        db_table = "cns_tratamiento_dental"
        indexes = [models.Index(fields=["no_exp", "pk_num"], name="cns_tratdent_patient_idx")]


# ── Bitacora de cambios (documento "Historia Clinica Unificada", seccion 6) ──

class ChangeLog(models.Model):
    """
    BITACORA_CAMBIOS: por que se dio de alta, se modifico o se dio de baja un
    registro de cualquier tabla del modelo, con el valor anterior y el nuevo
    (solo las columnas que cambiaron). Asi ninguna tabla necesita columnas de
    motivo propias.

    Reglas del documento para que no crezca de mas:
      - El motivo lo escribe la aplicacion (services/change_log_service.py),
        nunca un trigger: la base sabe que cambio, pero no por que.
      - Altas solo donde el motivo varia (identificador_paciente, fusiones);
        en las demas tablas el alta ya queda en usr_alta/fch_alta.
      - Sin autoguardados de borradores ni lecturas (las lecturas van en
        bitacora_acceso).

    No se edita ni se borra: es evidencia (NOM-024).
    """

    class Action(models.TextChoices):
        CREATE = "A", "Alta"
        UPDATE = "M", "Modificacion"
        DELETE = "B", "Baja"

    class Reason(models.TextChoices):
        SERMED_SYNC = "SINCRONIZACION SERMED", "Sincronizacion con SERMED"
        NEWBORN_REGISTRATION = "REGISTRO RN", "Registro de recien nacido"
        NEWBORN_LINK = "LIGA RN", "Liga de recien nacido con SERMED"
        MERGE = "FUSION", "Fusion de pacientes"
        CAPTURE = "CAPTURA", "Captura de un dato vacio"
        CORRECTION = "CORRECCION", "Correccion"
        MIGRATION_CONFLICT = "CONFLICTO MIGRACION", "Conflicto de migracion"
        MIGRATION = "MIGRACION", "Migracion del legado"
        CLINIC_CHANGE = "CAMBIO DE CLINICA EN SERMED", "Cambio de clinica en SERMED"

    id_change = models.BigAutoField(primary_key=True, db_column="id")
    table = models.CharField(max_length=40, db_column="tabla")
    # Llave legible del registro, p. ej. "PK_NUM|88731" o "id_paciente|15".
    key = models.CharField(max_length=80, db_column="llave")
    action = models.CharField(max_length=1, db_column="accion", choices=Action.choices)
    # Texto libre acotado: los valores de Reason son los conocidos, pero el
    # documento deja la lista abierta ("...").
    reason = models.CharField(max_length=60, db_column="motivo")
    previous_value = models.JSONField(
        db_column="valor_anterior", null=True, blank=True, encoder=DjangoJSONEncoder,
    )
    new_value = models.JSONField(
        db_column="valor_nuevo", null=True, blank=True, encoder=DjangoJSONEncoder,
    )
    # Usuario (id de SyUsuario como texto) o proceso (SYNC_SERMED, MIGRACION).
    user = models.CharField(max_length=40, db_column="usuario")
    occurred_at = models.DateTimeField(db_column="fecha_hora", default=timezone.now)

    class Meta:
        db_table = "cns_bitacora_cambios"
        ordering = ["occurred_at", "id_change"]
        indexes = [
            models.Index(fields=["table", "key", "occurred_at"], name="cns_bitacora_registro_idx"),
            models.Index(fields=["reason", "occurred_at"], name="cns_bitacora_motivo_idx"),
        ]
