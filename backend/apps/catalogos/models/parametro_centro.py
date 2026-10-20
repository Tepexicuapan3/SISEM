"""
Parametros operativos (reemplazo de ``ope_param`` del legado).

- ``ParametroDefinicion``: una fila por parametro (clave, tipo, valor general,
  limites). Agregar un parametro es una migracion de datos, no de esquema.
- ``ParametroCentro``: solo los centros cuyo valor difiere del general.

Regla: no se define ningun parametro que el codigo no lea. Las columnas de
``ope_param`` sin consumidor en SIRES se agregan cuando exista la regla que
las usa (fase 2: topes de receta y estudios, autorizacion por costo).
"""

from django.db import models


class ParametroDefinicion(models.Model):
    class Tipo(models.TextChoices):
        ENTERO = "ENTERO", "Entero"
        DECIMAL = "DECIMAL", "Decimal"
        BOOLEANO = "BOOLEANO", "Si/No"
        TEXTO = "TEXTO", "Texto"

    id = models.BigAutoField(primary_key=True, db_column="id_parametro")
    key = models.CharField(max_length=80, unique=True, db_column="clave")
    description = models.CharField(max_length=255, db_column="descripcion")
    module = models.CharField(max_length=40, db_column="modulo")
    value_type = models.CharField(max_length=10, choices=Tipo.choices, db_column="tp_valor")
    general_value = models.TextField(db_column="valor_general")
    min_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, db_column="valor_minimo")
    max_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, db_column="valor_maximo")
    # False para reglas que no dependen del centro (p. ej. topes de citas por
    # expediente, que se cuentan en todas las clinicas).
    allows_center_override = models.BooleanField(default=True, db_column="sw_por_centro")
    legacy_source = models.CharField(max_length=60, null=True, blank=True, db_column="origen_legado")
    is_active = models.BooleanField(default=True, db_column="est_activo")
    created_at = models.DateTimeField(auto_now_add=True, db_column="fch_alta")
    updated_at = models.DateTimeField(auto_now=True, db_column="fch_modf")
    updated_by_id = models.BigIntegerField(null=True, blank=True, db_column="usr_modf")

    class Meta:
        db_table = "cat_parametro"
        ordering = ["module", "key"]

    def __str__(self) -> str:
        return self.key


class ParametroCentro(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_parametro_centro")
    definition = models.ForeignKey(
        ParametroDefinicion, db_column="id_parametro", on_delete=models.PROTECT,
        related_name="center_values",
    )
    center = models.ForeignKey(
        "catalogos.CatCentroAtencion", db_column="id_centro_atencion", on_delete=models.PROTECT,
        related_name="+",
    )
    value = models.TextField(db_column="valor")
    created_at = models.DateTimeField(auto_now_add=True, db_column="fch_alta")
    created_by_id = models.BigIntegerField(null=True, blank=True, db_column="usr_alta")
    updated_at = models.DateTimeField(auto_now=True, db_column="fch_modf")
    updated_by_id = models.BigIntegerField(null=True, blank=True, db_column="usr_modf")

    class Meta:
        db_table = "cat_parametro_centro"
        constraints = [
            models.UniqueConstraint(fields=["definition", "center"], name="cat_parametro_centro_uq"),
        ]

    def __str__(self) -> str:
        return f"{self.definition_id}@{self.center_id}"
