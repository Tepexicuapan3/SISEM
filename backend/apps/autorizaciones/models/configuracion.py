"""Catalogos de configuracion del modulo (plan autorizadores-medicos, seccion 3.1).

- TipoAutorizacion: que se autoriza y como se comporta por defecto.
- ReglaCentro:      sobrescribe el comportamiento por centro (reemplaza ope_param del legado).
- Disparador:       que genera una solicitud (reemplaza AutorizaD.java del legado).
- Motivo:           motivos tipificados de rechazo, suspension, baja y cancelacion.
"""
from django.db import models
from django.db.models import Q

from .base import RegistroAuditable


class Modalidad(models.TextChoices):
    PRIMERO_VALIDO = "PRIMERO_VALIDO", "Primer autorizador válido"
    MULTIPLE = "MULTIPLE", "Varias aprobaciones"


class MetodoFirma(models.TextChoices):
    SIMPLE = "SIMPLE", "Contraseña propia"
    EFIRMA = "EFIRMA", "e.firma"


class TipoAutorizacion(RegistroAuditable):
    class Clave(models.TextChoices):
        LABORATORIO = "LAB", "Laboratorio"
        GABINETE = "GAB", "Gabinete"
        RECETA = "REC", "Recetas"
        CANCELACION_NOTA = "CNO", "Cancelación de nota"

    class TipoOrigen(models.TextChoices):
        RECETA = "RECETA", "Receta"
        PASE_LABORATORIO = "PASE_LABORATORIO", "Pase de laboratorio"
        PASE_GABINETE = "PASE_GABINETE", "Pase de gabinete"
        CANCELACION_NOTA = "CANCELACION_NOTA", "Cancelación de nota"

    id_tipo_autorizacion = models.BigAutoField(primary_key=True)
    clave = models.CharField(max_length=3, choices=Clave.choices)
    nombre = models.CharField(max_length=80)
    tipo_origen = models.CharField(max_length=20, choices=TipoOrigen.choices)
    modalidad_predeterminada = models.CharField(
        max_length=16, choices=Modalidad.choices, default=Modalidad.PRIMERO_VALIDO,
    )
    aprobaciones_requeridas = models.PositiveSmallIntegerField(default=1)
    # En MULTIPLE: un solo rechazo resuelve la solicitud como RECHAZADA.
    rechazo_resuelve_solicitud = models.BooleanField(default=True)
    permite_rechazo = models.BooleanField(default=True)
    horas_vigencia_solicitud = models.PositiveSmallIntegerField(default=72)
    # Sin respuesta tras estas horas: recordatorio y envio a los elegibles que faltaban (F7).
    horas_escalamiento = models.PositiveSmallIntegerField(default=24)
    dias_aviso_vencimiento = models.PositiveSmallIntegerField(default=15)
    metodo_firma_minimo = models.CharField(
        max_length=10, choices=MetodoFirma.choices, default=MetodoFirma.SIMPLE,
    )
    requiere_cedula = models.BooleanField(default=True)

    class Meta:
        db_table = "aut_tipo_autorizacion"
        constraints = [
            models.UniqueConstraint(
                fields=["clave"], condition=Q(fecha_baja__isnull=True),
                name="aut_tipo_autorizacion_clave_uq",
            ),
            models.CheckConstraint(
                condition=Q(aprobaciones_requeridas__gte=1, aprobaciones_requeridas__lte=10),
                name="aut_tipo_autorizacion_aprobaciones_ck",
            ),
            models.CheckConstraint(
                condition=~Q(modalidad_predeterminada="PRIMERO_VALIDO") | Q(aprobaciones_requeridas=1),
                name="aut_tipo_autorizacion_modalidad_ck",
            ),
            models.CheckConstraint(
                condition=Q(horas_vigencia_solicitud__gte=1),
                name="aut_tipo_autorizacion_horas_ck",
            ),
            models.CheckConstraint(
                condition=Q(horas_escalamiento__gte=1),
                name="aut_tipo_autorizacion_escala_ck",
            ),
        ]

    def __str__(self):
        return f"{self.clave} - {self.nombre}"


class ReglaCentro(RegistroAuditable):
    """Valores NULL heredan el predeterminado del tipo."""

    id_regla_centro = models.BigAutoField(primary_key=True)
    tipo_autorizacion = models.ForeignKey(
        TipoAutorizacion, on_delete=models.PROTECT,
        db_column="id_tipo_autorizacion", related_name="reglas_centro",
    )
    centro_atencion = models.ForeignKey(
        "catalogos.CatCentroAtencion", on_delete=models.PROTECT,
        db_column="id_centro_atencion", related_name="+",
    )
    modalidad = models.CharField(max_length=16, choices=Modalidad.choices, null=True, blank=True)
    aprobaciones_requeridas = models.PositiveSmallIntegerField(null=True, blank=True)
    horas_vigencia_solicitud = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "aut_regla_centro"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_autorizacion", "centro_atencion"], condition=Q(fecha_baja__isnull=True),
                name="aut_regla_centro_tipo_centro_uq",
            ),
            models.CheckConstraint(
                condition=Q(aprobaciones_requeridas__isnull=True)
                | Q(aprobaciones_requeridas__gte=1, aprobaciones_requeridas__lte=10),
                name="aut_regla_centro_aprobaciones_ck",
            ),
            models.CheckConstraint(
                condition=~Q(modalidad="PRIMERO_VALIDO")
                | Q(aprobaciones_requeridas__isnull=True)
                | Q(aprobaciones_requeridas=1),
                name="aut_regla_centro_modalidad_ck",
            ),
            models.CheckConstraint(
                condition=Q(horas_vigencia_solicitud__isnull=True) | Q(horas_vigencia_solicitud__gte=1),
                name="aut_regla_centro_horas_ck",
            ),
        ]


class Disparador(RegistroAuditable):
    class Clave(models.TextChoices):
        MEDICAMENTO_ESPECIAL = "MEDICAMENTO_ESPECIAL", "Medicamento de cuadro especial"
        MEDICAMENTO_CONTROLADO = "MEDICAMENTO_CONTROLADO", "Medicamento controlado"
        COSTO_RECETA = "COSTO_RECETA", "Costo total de la receta"
        ESTUDIO_MARCADO = "ESTUDIO_MARCADO", "Estudio que requiere autorización"
        CANCELACION_NOTA = "CANCELACION_NOTA", "Cancelación de nota"

    id_disparador = models.BigAutoField(primary_key=True)
    tipo_autorizacion = models.ForeignKey(
        TipoAutorizacion, on_delete=models.PROTECT,
        db_column="id_tipo_autorizacion", related_name="disparadores",
    )
    clave = models.CharField(max_length=24, choices=Clave.choices)
    # NULL = aplica a todos los centros.
    centro_atencion = models.ForeignKey(
        "catalogos.CatCentroAtencion", on_delete=models.PROTECT,
        db_column="id_centro_atencion", related_name="+", null=True, blank=True,
    )
    # Solo COSTO_RECETA: total de la receta a partir del cual se pide autorizacion.
    monto_umbral = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "aut_disparador"
        constraints = [
            models.CheckConstraint(
                condition=(Q(clave="COSTO_RECETA") & Q(monto_umbral__isnull=False))
                | (~Q(clave="COSTO_RECETA") & Q(monto_umbral__isnull=True)),
                name="aut_disparador_monto_ck",
            ),
            # Dos indices parciales en vez de COALESCE: NULL no choca en un UNIQUE.
            models.UniqueConstraint(
                fields=["tipo_autorizacion", "clave", "centro_atencion"],
                condition=Q(fecha_baja__isnull=True, centro_atencion__isnull=False),
                name="aut_disparador_centro_uq",
            ),
            models.UniqueConstraint(
                fields=["tipo_autorizacion", "clave"],
                condition=Q(fecha_baja__isnull=True, centro_atencion__isnull=True),
                name="aut_disparador_todos_uq",
            ),
        ]


class Motivo(RegistroAuditable):
    class Ambito(models.TextChoices):
        RECHAZO = "RECHAZO", "Rechazo de solicitud"
        SUSPENSION = "SUSPENSION", "Suspensión de autorizador"
        BAJA = "BAJA", "Baja de autorizador"
        CANCELACION = "CANCELACION", "Cancelación de solicitud"

    id_motivo = models.BigAutoField(primary_key=True)
    ambito = models.CharField(max_length=12, choices=Ambito.choices)
    clave = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=150)
    # "Otro": obliga a capturar el motivo en texto libre.
    requiere_descripcion_libre = models.BooleanField(default=False)

    class Meta:
        db_table = "aut_motivo"
        constraints = [
            models.UniqueConstraint(fields=["ambito", "clave"], name="aut_motivo_ambito_clave_uq"),
        ]

    def __str__(self):
        return f"{self.ambito}/{self.clave}"
