# Designacion de autorizadores (change cancelacion-nota-cascada, PR1).
#
# Reemplaza al catalogo plano `cat_autorizadores` (un renglon = un centro, con
# password en claro). Una DESIGNACION es (usuario, tipo de autorizacion, cargo,
# vigencia); su ALCANCE son N items, cada uno EXACTAMENTE uno de:
#   - CENTRO:      un centro de atencion especifico
#   - TIPO_CENTRO: todos los centros de un tipo (CLINICA/HOSPITAL/INSTITUTO),
#                  incluidos los que se den de alta despues
#   - GLOBAL:      explicito; nunca se infiere de la ausencia de datos
# La BD rechaza items ambiguos o vacios (CheckConstraint xor). La adscripcion
# del usuario (DetUsuario.id_centro_atencion) NO interviene: solo el alcance.
from django.db import models
from django.db.models import Q

from .base import CatalogBase

# Codigo del tipo de autorizacion "cancelacion de nota" en cat_tpautorizacion
# (cve_tpautorizacion es CharField(max_length=2)). Lo siembra la migracion
# 0038 de forma idempotente por codigo.
TIPO_CANCELAR_NOTA = "CN"
TIPO_CANCELAR_NOTA_NOMBRE = "Cancelación de nota"


class DesignacionAutorizador(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_designacion")
    user = models.ForeignKey(
        "authentication.SyUsuario",
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="designaciones_autorizador",
    )
    authorization_type = models.ForeignKey(
        "catalogos.TpAutorizacion",
        on_delete=models.PROTECT,
        db_column="id_tpautorizacion",
        related_name="designaciones",
    )
    position = models.CharField(max_length=60, db_column="cargo")
    start_date = models.DateField(db_column="fe_inicio")
    end_date = models.DateField(db_column="fe_fin", null=True, blank=True)
    official_letter = models.CharField(max_length=100, db_column="no_oficio", null=True, blank=True)
    # Solo para impresion; no interviene en ninguna decision de autorizacion.
    signature_image = models.CharField(max_length=200, db_column="img_firma", null=True, blank=True)
    # Trazabilidad de la copia desde cat_autorizadores (migracion 0039).
    origin_authorizer_id = models.BigIntegerField(db_column="id_autorizador_origen", null=True, blank=True)

    class Meta:
        db_table = "cat_designacion_autorizador"
        managed = True
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="cat_desig_aut_vigencia_ck",
            ),
            models.UniqueConstraint(
                fields=["user", "authorization_type"],
                condition=Q(is_active=True, deleted_at__isnull=True),
                name="cat_desig_aut_una_activa",
            ),
        ]
        indexes = [
            models.Index(fields=["authorization_type", "is_active"], name="cat_desig_aut_tipo_act_idx"),
        ]


class DesignacionAlcance(CatalogBase):
    class Alcance(models.TextChoices):
        CENTRO = "CENTRO", "Centro"
        TIPO_CENTRO = "TIPO_CENTRO", "Tipo de centro"
        GLOBAL = "GLOBAL", "Global"

    # Mismos valores que CatCentroAtencion.TipoCentro (no se importa para no
    # acoplar el modulo de modelos con el de centros).
    TIPOS_CENTRO_VALIDOS = ("CLINICA", "HOSPITAL", "INSTITUTO")

    id = models.BigAutoField(primary_key=True, db_column="id_alcance")
    designation = models.ForeignKey(
        DesignacionAutorizador,
        on_delete=models.PROTECT,
        db_column="id_designacion",
        related_name="scopes",
    )
    scope_type = models.CharField(max_length=12, choices=Alcance.choices, db_column="tp_alcance")
    center = models.ForeignKey(
        "catalogos.CatCentroAtencion",
        on_delete=models.PROTECT,
        db_column="id_centro_atencion",
        related_name="alcances_designacion",
        null=True,
        blank=True,
    )
    center_type = models.CharField(max_length=20, db_column="tipo_centro", null=True, blank=True)

    class Meta:
        db_table = "det_designacion_alcance"
        managed = True
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(scope_type="CENTRO", center__isnull=False, center_type__isnull=True)
                    | Q(
                        scope_type="TIPO_CENTRO",
                        center__isnull=True,
                        # isnull=False explicito: NULL IN (...) da NULL y un
                        # CHECK con resultado NULL PASA (hueco de 3 valores).
                        center_type__isnull=False,
                        center_type__in=["CLINICA", "HOSPITAL", "INSTITUTO"],
                    )
                    | Q(scope_type="GLOBAL", center__isnull=True, center_type__isnull=True)
                ),
                name="det_desig_alcance_xor",
            ),
            models.UniqueConstraint(
                fields=["designation", "center"],
                condition=Q(scope_type="CENTRO", is_active=True, deleted_at__isnull=True),
                name="det_desig_alcance_centro_uq",
            ),
            models.UniqueConstraint(
                fields=["designation", "center_type"],
                condition=Q(scope_type="TIPO_CENTRO", is_active=True, deleted_at__isnull=True),
                name="det_desig_alcance_tipo_uq",
            ),
            models.UniqueConstraint(
                fields=["designation"],
                condition=Q(scope_type="GLOBAL", is_active=True, deleted_at__isnull=True),
                name="det_desig_alcance_global_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["center"], name="det_desig_alc_centro_idx"),
            models.Index(fields=["center_type"], name="det_desig_alc_tipo_idx"),
        ]
