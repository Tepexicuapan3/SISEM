"""
apps/impresion/models.py
============================
Bitacora de impresiones (append-only) y consecutivo de copias por documento.

Sin ``JSONField`` a proposito (en Postgres real es jsonb y rompe filtros ORM
sobre columnas json).
"""

from django.db import models


class PrintLog(models.Model):
    """Una fila por PDF emitido. ``copy_number`` 1 = ORIGINAL, >1 = REIMPRESION."""

    class Tipo(models.TextChoices):
        ORIGINAL = "ORIGINAL", "Original"
        REIMPRESION = "REIMPRESION", "Reimpresion"

    id = models.BigAutoField(primary_key=True, db_column="id_impresion")
    documento = models.CharField(max_length=30)  # ficha | receta | nota
    resource_id = models.BigIntegerField(db_column="id_recurso")
    folio = models.CharField(max_length=50, blank=True, default="")
    no_exp = models.CharField(max_length=20, null=True, blank=True)
    tp_paciente = models.CharField(max_length=10, null=True, blank=True)
    copy_number = models.PositiveIntegerField(db_column="copia")
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    user = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="id_usuario",
        on_delete=models.PROTECT,
        related_name="impresiones",
    )
    user_code = models.CharField(max_length=50, db_column="cd_usuario")
    printed_at = models.DateTimeField(db_column="fch_impresion", auto_now_add=True)
    sha256 = models.CharField(max_length=64, db_column="hash_sha256")
    engine = models.CharField(max_length=10, default="weasy")  # weasy | docx
    ip = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default="")
    cancelled = models.BooleanField(db_column="cancelada", default=False)

    class Meta:
        db_table = "imp_bitacora_impresion"
        constraints = [
            models.UniqueConstraint(
                fields=["documento", "resource_id", "copy_number"],
                name="uq_imp_doc_recurso_copia",
            ),
        ]
        indexes = [
            models.Index(
                fields=["documento", "resource_id"], name="idx_imp_doc_recurso"
            ),
            models.Index(fields=["no_exp", "printed_at"], name="idx_imp_exp_fch"),
        ]


class PrintCounter(models.Model):
    """Ultima copia emitida por (documento, recurso). Se bloquea con
    SELECT ... FOR UPDATE para asignar el siguiente numero de copia sin
    carreras (mismo patron que ``PrescriptionFolioCounter``)."""

    id = models.BigAutoField(primary_key=True)
    documento = models.CharField(max_length=30)
    resource_id = models.BigIntegerField(db_column="id_recurso")
    last_copy = models.PositiveIntegerField(db_column="ultima_copia", default=0)

    class Meta:
        db_table = "imp_consecutivo_impresion"
        constraints = [
            models.UniqueConstraint(
                fields=["documento", "resource_id"],
                name="uq_imp_counter_doc_recurso",
            ),
        ]
