from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone


class BitacoraSyncExpediente(models.Model):
    """
    Cada actualizacion de un expediente desde SERMED (Oracle -> replica
    "expedientes" -> pacientes de SIRES): quien la pidio, desde donde, cuando
    y con que resultado.

    Vive en la base principal y NUNCA en la replica: sync_service copia todas
    las columnas de las tablas replicadas y una columna ajena a Oracle rompe
    el sync (incidente 2026-09-17).

    Append-only (trigger en Postgres, migracion 0014). Se crea EN_CURSO al
    empezar, asi queda rastro aunque el proceso muera a la mitad, y se cierra
    una sola vez con el resultado; despues ya no cambia.
    """

    class Origen(models.TextChoices):
        BOTON = "BOTON", "Boton Actualizar"
        COMANDO = "COMANDO", "Comando de consola"
        AUTOMATICO = "AUTOMATICO", "Proceso automatico"

    class Resultado(models.TextChoices):
        EN_CURSO = "EN_CURSO", "En curso"
        OK = "OK", "Completa"
        # La replica quedo al dia pero la sincronizacion de pacientes fallo.
        PARCIAL = "PARCIAL", "Parcial"
        # No se aplico nada: la replica se revirtio completa.
        ERROR = "ERROR", "Error"
        # Otro proceso ya estaba actualizando el mismo expediente.
        OCUPADO = "OCUPADO", "Expediente ocupado"

    id = models.BigAutoField(primary_key=True, db_column="id")
    no_exp = models.CharField(max_length=20)
    usuario = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="id_usuario",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Login al momento de la operacion (se conserva aunque el usuario cambie
    # o se de de baja) o el nombre del proceso cuando no hay usuario.
    cd_usuario = models.CharField(max_length=50)
    origen = models.CharField(max_length=12, choices=Origen.choices)
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    request_id = models.CharField(max_length=64, null=True, blank=True)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(max_length=10, choices=Resultado.choices, default=Resultado.EN_CURSO)
    # {"tablas": {"cat_empleados": {"insertados": 0, ...}}, "pacientes": {...}}
    conteos = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    errores = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    class Meta:
        db_table = "bitacora_sync_expediente"
        managed = True
        ordering = ["-fecha_inicio", "-id"]
        indexes = [
            models.Index(fields=["no_exp", "fecha_inicio"], name="bitacora_sync_exp_idx"),
            models.Index(fields=["resultado", "fecha_inicio"], name="bitacora_sync_resultado_idx"),
        ]


class BitacoraReplicaSermed(models.Model):
    """
    Valor anterior y nuevo de cada fila que una actualizacion cambio en la
    replica de SERMED (cat_empleados, cat_familiar, licencias, fotos...).
    La replica solo guarda el valor actual y el sync sobrescribe o borra
    fisico; esta tabla es la que permite responder "¿estaba vigente el dia
    que se le atendio?" (politica de retencion NOM-024: nada se pierde).

    Alta (A): fila completa nueva. Modificacion (M): solo las columnas que
    cambiaron. Baja (B): fila completa borrada. Los binarios (fotos) se
    guardan como hash, no la imagen. Append-only (trigger, migracion 0014).
    """

    class Accion(models.TextChoices):
        ALTA = "A", "Alta"
        MODIFICACION = "M", "Modificacion"
        BAJA = "B", "Baja"

    id = models.BigAutoField(primary_key=True, db_column="id")
    sync = models.ForeignKey(
        BitacoraSyncExpediente,
        db_column="id_sync",
        on_delete=models.PROTECT,
        related_name="cambios",
    )
    tabla = models.CharField(max_length=40)
    # Llave legible del registro, p. ej. "no_exp|40041" o "pk_num|88731".
    llave = models.CharField(max_length=120)
    accion = models.CharField(max_length=1, choices=Accion.choices)
    valor_anterior = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    valor_nuevo = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    fecha_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "bitacora_replica_sermed"
        managed = True
        ordering = ["fecha_hora", "id"]
        indexes = [
            models.Index(fields=["tabla", "llave", "fecha_hora"], name="bitacora_replica_reg_idx"),
        ]
