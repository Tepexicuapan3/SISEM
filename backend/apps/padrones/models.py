"""
apps/padrones/models.py
===========================
Padrones clinicos (P-04 del legado): inscripcion de un paciente al programa
de control de cronico-degenerativos o al registro de discapacidad.

Es distinto del antecedente personal (cns_antecedente_personal): el
antecedente dice QUE TIENE el paciente; la inscripcion dice que esta EN EL
PROGRAMA (activa el aviso en consulta y el tope de receta ampliado).

Diferencias con el legado (det_cronicodeg / det_cronicodegbaj /
det_discapacitados), a proposito:
- La baja es por inscripcion, no del paciente completo, y con motivo de
  catalogo (cat_motivo_baja_padron) que incluye motivos clinicos.
- Llaves foraneas reales (paciente, CIE-10, centro, usuario) en vez de
  textos sueltos; una sola inscripcion activa por paciente y padecimiento.
- La baja es logica: la fila queda como historial.
"""

from django.db import models


class RegistryStatus(models.TextChoices):
    ACTIVO = "activo", "Activo"
    BAJA = "baja", "Baja"


class RegistryEnrollmentBase(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_inscripcion")
    # Mismo criterio que los registros permanentes del paciente
    # (PatientRecordBase): no_exp/pk_num + FK al paciente.
    patient = models.ForeignKey(
        "consulta_medica.Patient", db_column="id_paciente", on_delete=models.PROTECT,
        related_name="+",
    )
    center = models.ForeignKey(
        "catalogos.CatCentroAtencion", db_column="id_centro_atencion", on_delete=models.PROTECT,
        related_name="+",
    )
    enrolled_on = models.DateField(db_column="fe_inscripcion")
    enrolled_by = models.ForeignKey(
        "authentication.SyUsuario", db_column="usr_inscribe", on_delete=models.PROTECT,
        related_name="+",
    )
    notes = models.CharField(max_length=500, db_column="observaciones", null=True, blank=True)
    status = models.CharField(
        max_length=10, db_column="estatus", choices=RegistryStatus.choices,
        default=RegistryStatus.ACTIVO, db_index=True,
    )
    discharge_reason = models.ForeignKey(
        "catalogos.MotivoBajaPadron", db_column="id_motivo_baja_padron", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    discharge_detail = models.CharField(max_length=500, db_column="detalle_baja", null=True, blank=True)
    discharged_on = models.DateField(db_column="fe_baja", null=True, blank=True)
    discharged_by = models.ForeignKey(
        "authentication.SyUsuario", db_column="usr_baja", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)

    class Meta:
        abstract = True


class ChronicEnrollment(RegistryEnrollmentBase):
    cie = models.ForeignKey(
        "catalogos.CatCies", db_column="clave_cie", on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        db_table = "cns_padron_cronico"
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "cie"], condition=models.Q(status="activo"),
                name="cns_padron_cronico_activo_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["center", "status"], name="cns_padcron_centro_idx"),
        ]


class ChronicProgram(models.Model):
    """
    Programa de control de cronicos (diabetes, hipertension...). Agrupa los
    CIE-10 que lo disparan: con el se sugiere inscribir al paciente cuando el
    medico elige uno de esos diagnosticos (docs/plans/cronicos-aviso-consulta.md).
    """

    id = models.BigAutoField(primary_key=True, db_column="id_programa_cronico")
    code = models.CharField(max_length=20, unique=True, db_column="clave")
    name = models.CharField(max_length=100, db_column="nombre")
    # Cada cuantos dias toca el siguiente control (docs/plans/cronicos-control.md).
    control_every_days = models.PositiveSmallIntegerField(default=90, db_column="dias_control")
    is_active = models.BooleanField(default=True, db_column="est_activo")
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)

    class Meta:
        db_table = "cat_programa_cronico"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ChronicProgramCie(models.Model):
    """Prefijo CIE-10 de un programa, sin punto (E11 cubre E11.9 y E119)."""

    id = models.BigAutoField(primary_key=True, db_column="id_programa_cronico_cie")
    program = models.ForeignKey(
        ChronicProgram, db_column="id_programa_cronico", on_delete=models.PROTECT,
        related_name="cie_prefixes",
    )
    # Un prefijo pertenece a un solo programa: si no, la sugerencia seria ambigua.
    cie_prefix = models.CharField(max_length=8, unique=True, db_column="prefijo_cie")
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)

    class Meta:
        db_table = "cat_programa_cronico_cie"


class DisabilityEnrollment(RegistryEnrollmentBase):
    disability = models.ForeignKey(
        "catalogos.Discapacidades", db_column="id_discapacidad", on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "cns_padron_discapacidad"
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "disability"], condition=models.Q(status="activo"),
                name="cns_padron_discap_activo_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["center", "status"], name="cns_paddisc_centro_idx"),
        ]


class ControlParameter(models.TextChoices):
    """Parametros del control de cronicos. De donde sale cada uno (somatometria
    o captura manual) lo define control_cronico_usecase.PARAMETERS."""

    TA_SISTOLICA = "ta_sistolica", "Presión sistólica"
    TA_DIASTOLICA = "ta_diastolica", "Presión diastólica"
    GLUCOSA_CAPILAR = "glucosa_capilar", "Glucosa capilar"
    IMC = "imc", "IMC"
    PESO = "peso", "Peso"
    CINTURA = "cintura", "Cintura"
    HBA1C = "hba1c", "Hemoglobina glucosilada (HbA1c)"
    COLESTEROL_TOTAL = "colesterol_total", "Colesterol total"
    LDL = "ldl", "Colesterol LDL"
    TRIGLICERIDOS = "trigliceridos", "Triglicéridos"


class ChronicControlGoal(models.Model):
    """Meta de un parametro en un programa (limites inclusivos)."""

    id = models.BigAutoField(primary_key=True, db_column="id_meta_control")
    program = models.ForeignKey(
        ChronicProgram, db_column="id_programa_cronico", on_delete=models.PROTECT, related_name="goals",
    )
    parameter = models.CharField(max_length=20, choices=ControlParameter.choices, db_column="parametro")
    min_value = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, db_column="valor_min")
    max_value = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, db_column="valor_max")
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)

    class Meta:
        db_table = "cat_meta_control_cronico"
        constraints = [
            models.UniqueConstraint(fields=["program", "parameter"], name="cat_meta_ctl_prog_param_uq"),
            models.CheckConstraint(
                condition=models.Q(min_value__isnull=False) | models.Q(max_value__isnull=False),
                name="cat_meta_ctl_algun_limite",
            ),
        ]


class ControlStatus(models.TextChoices):
    SIN_DATOS = "sin_datos", "Sin datos"
    DESCONTROLADO = "descontrolado", "Descontrolado"
    INCOMPLETO = "incompleto", "Incompleto"
    CONTROLADO = "controlado", "Controlado"


class Adherence(models.TextChoices):
    BUENA = "buena", "Buena"
    REGULAR = "regular", "Regular"
    MALA = "mala", "Mala"


class ChronicControl(models.Model):
    """
    Control de un programa en una consulta. Solo se agrega: no se edita ni se
    borra (una correccion sera un addendum). Uno por programa y visita.
    """

    id = models.BigAutoField(primary_key=True, db_column="id_control_cronico")
    patient = models.ForeignKey(
        "consulta_medica.Patient", db_column="id_paciente", on_delete=models.PROTECT, related_name="+",
    )
    program = models.ForeignKey(
        ChronicProgram, db_column="id_programa_cronico", on_delete=models.PROTECT, related_name="+",
    )
    visit = models.ForeignKey(
        "recepcion.Visit", db_column="id_visit", on_delete=models.PROTECT, related_name="+",
    )
    center = models.ForeignKey(
        "catalogos.CatCentroAtencion", db_column="id_centro_atencion", on_delete=models.PROTECT,
        related_name="+",
    )
    control_on = models.DateField(db_column="fe_control")
    status = models.CharField(max_length=15, choices=ControlStatus.choices, db_column="estatus")
    next_control_on = models.DateField(db_column="fe_proximo_control")
    adherence = models.CharField(
        max_length=10, choices=Adherence.choices, null=True, blank=True, db_column="adherencia",
    )
    notes = models.CharField(max_length=500, null=True, blank=True, db_column="observaciones")
    registered_by = models.ForeignKey(
        "authentication.SyUsuario", db_column="usr_registra", on_delete=models.PROTECT, related_name="+",
    )
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)

    class Meta:
        db_table = "cns_control_cronico"
        constraints = [
            models.UniqueConstraint(fields=["program", "visit"], name="cns_control_cronico_visita_uq"),
        ]
        indexes = [
            models.Index(fields=["patient", "program", "control_on"], name="cns_ctlcron_pac_prog_idx"),
            models.Index(fields=["center", "next_control_on"], name="cns_ctlcron_centro_prox_idx"),
        ]


class MeasurementSource(models.TextChoices):
    SOMATOMETRIA = "somatometria", "Somatometría"
    MANUAL = "manual", "Captura manual"


class ChronicControlMeasurement(models.Model):
    """Valor de un parametro en el control, con la meta vigente copiada."""

    id = models.BigAutoField(primary_key=True, db_column="id_control_medicion")
    control = models.ForeignKey(
        ChronicControl, db_column="id_control_cronico", on_delete=models.PROTECT, related_name="measurements",
    )
    parameter = models.CharField(max_length=20, choices=ControlParameter.choices, db_column="parametro")
    value = models.DecimalField(max_digits=7, decimal_places=2, db_column="valor")
    unit = models.CharField(max_length=10, db_column="unidad")
    source = models.CharField(max_length=15, choices=MeasurementSource.choices, db_column="fuente")
    goal_min = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, db_column="meta_min")
    goal_max = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, db_column="meta_max")
    in_goal = models.BooleanField(null=True, blank=True, db_column="en_meta")

    class Meta:
        db_table = "cns_control_cronico_medicion"
        constraints = [
            models.UniqueConstraint(fields=["control", "parameter"], name="cns_ctlcron_med_param_uq"),
        ]
