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
    no_exp = models.CharField(max_length=20, db_column="no_exp")
    pk_num = models.IntegerField(db_column="pk_num", default=0)
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
            models.Index(fields=["no_exp", "pk_num"], name="cns_padcron_paciente_idx"),
            models.Index(fields=["center", "status"], name="cns_padcron_centro_idx"),
        ]


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
            models.Index(fields=["no_exp", "pk_num"], name="cns_paddisc_paciente_idx"),
            models.Index(fields=["center", "status"], name="cns_paddisc_centro_idx"),
        ]
