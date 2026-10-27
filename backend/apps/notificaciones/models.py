"""Notificaciones a usuarios de SIRES (modulo tecnico, prefijo ntf_).

Una Notificacion por usuario destinatario; una Entrega por canal con su
resultado (quien, a quien, cuando y si se entrego). El cuerpo nunca lleva
datos clinicos: solo lo necesario para identificar el asunto y un enlace
interno que solo navega.
"""
from django.db import models
from django.db.models import Q


class Notificacion(models.Model):
    class Prioridad(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        URGENTE = "URGENTE", "Urgente"

    id_notificacion = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        "authentication.SyUsuario", on_delete=models.PROTECT, db_column="id_usuario", related_name="notificaciones",
    )
    # AUT_SOLICITADA, AUT_RESUELTA, AUT_ATENDIDA_POR_OTRO, AUT_VENCIDA, AUT_CANCELADA, AUT_SIN_ELEGIBLES
    categoria = models.CharField(max_length=40)
    titulo = models.CharField(max_length=150)
    cuerpo = models.CharField(max_length=500)
    tipo_recurso = models.CharField(max_length=40)
    referencia_recurso = models.CharField(max_length=64)  # uuid publico, nunca un id secuencial
    url_accion = models.CharField(max_length=255)  # ruta interna del frontend
    prioridad = models.CharField(max_length=8, choices=Prioridad.choices, default=Prioridad.NORMAL)
    fecha_lectura = models.DateTimeField(null=True, blank=True)
    fecha_archivo = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    id_usuario_envio = models.BigIntegerField(null=True, blank=True)  # NULL = sistema

    class Meta:
        db_table = "ntf_notificacion"
        indexes = [
            models.Index(
                fields=["usuario", "fecha_lectura", "-fecha_creacion"],
                condition=Q(fecha_archivo__isnull=True),
                name="ntf_notificacion_bandeja_idx",
            ),
            models.Index(fields=["tipo_recurso", "referencia_recurso"], name="ntf_notificacion_recurso_idx"),
        ]


class Entrega(models.Model):
    class Canal(models.TextChoices):
        INTERNA = "INTERNA", "Bandeja interna"
        TIEMPO_REAL = "TIEMPO_REAL", "Tiempo real"
        CORREO = "CORREO", "Correo electrónico"

    class Estatus(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADA = "ENVIADA", "Enviada"
        FALLIDA = "FALLIDA", "Fallida"
        OMITIDA = "OMITIDA", "Omitida"

    id_entrega = models.BigAutoField(primary_key=True)
    notificacion = models.ForeignKey(
        Notificacion, on_delete=models.PROTECT, db_column="id_notificacion", related_name="entregas",
    )
    canal = models.CharField(max_length=12, choices=Canal.choices)
    destino_enmascarado = models.CharField(max_length=120, null=True, blank=True)
    estatus = models.CharField(max_length=10, choices=Estatus.choices, default=Estatus.PENDIENTE)
    intentos = models.PositiveSmallIntegerField(default=0)
    detalle_error = models.CharField(max_length=255, null=True, blank=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ntf_entrega"
        constraints = [
            models.UniqueConstraint(fields=["notificacion", "canal"], name="ntf_entrega_notificacion_canal_uq"),
        ]
