"""Autorizadores medicos (plan autorizadores-medicos, seccion 3.2).

Autorizador (1 por usuario) -> AutorizadorTipo (1 por tipo de autorizacion)
-> AutorizadorAlcance (centros que cubre ese tipo: CENTRO | TIPO_CENTRO | GLOBAL).

El estatus (ACTIVO/SUSPENDIDO/INACTIVO) se guarda; el estado de vigencia
(vigente, por vencer, vencido) se calcula al momento. Quitar un tipo o un
centro es baja logica: las decisiones ya firmadas siguen apuntando a el.
"""
from django.db import models
from django.db.models import F, Q

from .base import RegistroAuditable
from .configuracion import Motivo, TipoAutorizacion

TIPOS_CENTRO_VALIDOS = ("CLINICA", "HOSPITAL", "INSTITUTO")


class Autorizador(RegistroAuditable):
    class Estatus(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        SUSPENDIDO = "SUSPENDIDO", "Suspendido"
        INACTIVO = "INACTIVO", "Inactivo"

    id_autorizador = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        "authentication.SyUsuario", on_delete=models.PROTECT,
        db_column="id_usuario", related_name="registros_autorizador",
    )
    # La cedula NO se guarda aqui: se captura en Usuarios (det_usuario_cedulas)
    # y esa pantalla borra y recrea las filas en cada edicion, asi que una FK
    # quedaria rota. Se lee del usuario al operar y se copia como texto en la
    # decision firmada.
    cargo = models.CharField(max_length=80, null=True, blank=True)
    numero_oficio = models.CharField(max_length=100, null=True, blank=True)
    estatus = models.CharField(max_length=12, choices=Estatus.choices, default=Estatus.ACTIVO)
    fecha_inicio_vigencia = models.DateField()
    fecha_fin_vigencia = models.DateField()
    motivo_estatus = models.ForeignKey(
        Motivo, on_delete=models.PROTECT,
        db_column="id_motivo_estatus", related_name="+", null=True, blank=True,
    )
    descripcion_motivo_estatus = models.CharField(max_length=255, null=True, blank=True)
    # Suspension temporal con fin conocido (opcional).
    fecha_fin_suspension = models.DateField(null=True, blank=True)
    # Bloqueo optimista: la pantalla manda la version que edito.
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "aut_autorizador"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"], condition=Q(fecha_baja__isnull=True),
                name="aut_autorizador_usuario_uq",
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin_vigencia__gte=F("fecha_inicio_vigencia")),
                name="aut_autorizador_vigencia_ck",
            ),
            models.CheckConstraint(
                condition=Q(estatus="SUSPENDIDO") | Q(fecha_fin_suspension__isnull=True),
                name="aut_autorizador_fin_suspension_ck",
            ),
            models.CheckConstraint(
                condition=Q(estatus="ACTIVO") | Q(motivo_estatus__isnull=False),
                name="aut_autorizador_motivo_estatus_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["estatus", "fecha_fin_vigencia"], name="aut_autorizador_estatus_idx"),
        ]


class AutorizadorTipo(RegistroAuditable):
    """Permiso independiente por tipo. Vigencia NULL = hereda la de la cabecera."""

    id_autorizador_tipo = models.BigAutoField(primary_key=True)
    autorizador = models.ForeignKey(
        Autorizador, on_delete=models.PROTECT,
        db_column="id_autorizador", related_name="tipos",
    )
    tipo_autorizacion = models.ForeignKey(
        TipoAutorizacion, on_delete=models.PROTECT,
        db_column="id_tipo_autorizacion", related_name="autorizadores",
    )
    fecha_inicio_vigencia = models.DateField(null=True, blank=True)
    fecha_fin_vigencia = models.DateField(null=True, blank=True)
    # Trazabilidad de la migracion desde cat_designacion_autorizador (F8);
    # NULL en los tipos dados de alta en la pantalla nueva.
    id_designacion_origen = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "aut_autorizador_tipo"
        constraints = [
            models.UniqueConstraint(
                fields=["autorizador", "tipo_autorizacion"],
                condition=Q(esta_activo=True, fecha_baja__isnull=True),
                name="aut_autorizador_tipo_uq",
            ),
            # Una designacion vieja se migra una sola vez.
            models.UniqueConstraint(
                fields=["id_designacion_origen"],
                condition=Q(id_designacion_origen__isnull=False),
                name="aut_autorizador_tipo_origen_uq",
            ),
            models.CheckConstraint(
                condition=Q(fecha_inicio_vigencia__isnull=True)
                | Q(fecha_fin_vigencia__isnull=True)
                | Q(fecha_fin_vigencia__gte=F("fecha_inicio_vigencia")),
                name="aut_autorizador_tipo_vigencia_ck",
            ),
        ]


class AutorizadorAlcance(RegistroAuditable):
    class TipoAlcance(models.TextChoices):
        CENTRO = "CENTRO", "Centro específico"
        TIPO_CENTRO = "TIPO_CENTRO", "Todos los centros de un tipo"
        GLOBAL = "GLOBAL", "Todos los centros"

    id_autorizador_alcance = models.BigAutoField(primary_key=True)
    autorizador_tipo = models.ForeignKey(
        AutorizadorTipo, on_delete=models.PROTECT,
        db_column="id_autorizador_tipo", related_name="alcances",
    )
    tipo_alcance = models.CharField(max_length=12, choices=TipoAlcance.choices)
    centro_atencion = models.ForeignKey(
        "catalogos.CatCentroAtencion", on_delete=models.PROTECT,
        db_column="id_centro_atencion", related_name="+", null=True, blank=True,
    )
    tipo_centro = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "aut_autorizador_alcance"
        constraints = [
            # Exactamente uno. isnull=False explicito en TIPO_CENTRO: NULL IN (...)
            # da NULL y un CHECK con resultado NULL pasa.
            models.CheckConstraint(
                condition=(
                    Q(tipo_alcance="CENTRO", centro_atencion__isnull=False, tipo_centro__isnull=True)
                    | Q(
                        tipo_alcance="TIPO_CENTRO",
                        centro_atencion__isnull=True,
                        tipo_centro__isnull=False,
                        tipo_centro__in=list(TIPOS_CENTRO_VALIDOS),
                    )
                    | Q(tipo_alcance="GLOBAL", centro_atencion__isnull=True, tipo_centro__isnull=True)
                ),
                name="aut_autorizador_alcance_xor_ck",
            ),
            models.UniqueConstraint(
                fields=["autorizador_tipo", "centro_atencion"],
                condition=Q(tipo_alcance="CENTRO", esta_activo=True, fecha_baja__isnull=True),
                name="aut_autorizador_alcance_centro_uq",
            ),
            models.UniqueConstraint(
                fields=["autorizador_tipo", "tipo_centro"],
                condition=Q(tipo_alcance="TIPO_CENTRO", esta_activo=True, fecha_baja__isnull=True),
                name="aut_autorizador_alcance_tipo_uq",
            ),
            models.UniqueConstraint(
                fields=["autorizador_tipo"],
                condition=Q(tipo_alcance="GLOBAL", esta_activo=True, fecha_baja__isnull=True),
                name="aut_autorizador_alcance_global_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["centro_atencion"], name="aut_aut_alcance_centro_idx"),
            models.Index(fields=["tipo_centro"], name="aut_aut_alcance_tipo_idx"),
        ]


class AutorizadorMovimiento(models.Model):
    """Historial de negocio. Solo INSERT: en PostgreSQL un trigger rechaza
    UPDATE y DELETE (migracion 0003)."""

    class TipoMovimiento(models.TextChoices):
        ALTA = "ALTA", "Alta"
        EDICION = "EDICION", "Edición de datos"
        RENOVACION = "RENOVACION", "Renovación de vigencia"
        SUSPENSION = "SUSPENSION", "Suspensión"
        REACTIVACION = "REACTIVACION", "Reactivación"
        BAJA = "BAJA", "Baja"
        ALTA_TIPO = "ALTA_TIPO", "Tipo de autorización asignado"
        BAJA_TIPO = "BAJA_TIPO", "Tipo de autorización retirado"
        ALTA_CENTRO = "ALTA_CENTRO", "Centro asignado"
        BAJA_CENTRO = "BAJA_CENTRO", "Centro retirado"
        VENCIMIENTO = "VENCIMIENTO", "Vencimiento de vigencia"
        AVISO_POR_VENCER = "AVISO_POR_VENCER", "Aviso de vigencia por vencer"

    id_movimiento = models.BigAutoField(primary_key=True)
    autorizador = models.ForeignKey(
        Autorizador, on_delete=models.PROTECT,
        db_column="id_autorizador", related_name="movimientos",
    )
    tipo_movimiento = models.CharField(max_length=20, choices=TipoMovimiento.choices)
    motivo = models.ForeignKey(
        Motivo, on_delete=models.PROTECT, db_column="id_motivo", related_name="+",
        null=True, blank=True,
    )
    descripcion_motivo = models.CharField(max_length=255, null=True, blank=True)
    datos_anteriores = models.JSONField(null=True, blank=True)
    datos_nuevos = models.JSONField(null=True, blank=True)
    # NULL solo cuando lo registra un proceso automatico (VENCIMIENTO).
    id_usuario_responsable = models.BigIntegerField(null=True, blank=True)
    fecha_movimiento = models.DateTimeField(auto_now_add=True)
    identificador_peticion = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "aut_autorizador_movimiento"
        indexes = [
            models.Index(fields=["autorizador", "-fecha_movimiento"], name="aut_autorizador_mov_idx"),
        ]
