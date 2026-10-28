"""Solicitudes de autorizacion (plan autorizadores-medicos, seccion 3.3).

Solicitud -> Items (que se autoriza), Destinatarios (a quien se envio),
Decisiones (firmadas, solo insercion) y Transiciones (historial de estados,
solo insercion).

Las aprobaciones vigentes NO se guardan como contador: se cuentan las
decisiones APROBAR cuyo hash_contenido coincide con el de la solicitud. Si el
documento de origen cambia, el hash cambia y las aprobaciones previas dejan
de contar sin tener que modificar ninguna decision firmada.
"""
import uuid

from django.db import models
from django.db.models import Q

from .autorizador import Autorizador, AutorizadorTipo
from .base import RegistroAuditable
from .configuracion import MetodoFirma, Modalidad, Motivo, TipoAutorizacion


class Solicitud(RegistroAuditable):
    class Estatus(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        AUTORIZADA = "AUTORIZADA", "Autorizada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        VENCIDA = "VENCIDA", "Vencida"
        CANCELADA = "CANCELADA", "Cancelada"

    class Prioridad(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        URGENTE = "URGENTE", "Urgente"

    id_solicitud = models.BigAutoField(primary_key=True)
    # Identificador que viaja en enlaces y notificaciones (nunca el id secuencial).
    uuid_publico = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    folio = models.CharField(max_length=32, unique=True)
    tipo_autorizacion = models.ForeignKey(
        TipoAutorizacion, on_delete=models.PROTECT, db_column="id_tipo_autorizacion", related_name="solicitudes",
    )
    # Documento de origen en su dominio dueño (sin FK cross-domain).
    tipo_origen = models.CharField(max_length=20, choices=TipoAutorizacion.TipoOrigen.choices)
    id_origen = models.BigIntegerField()
    folio_origen = models.CharField(max_length=40, null=True, blank=True)
    centro_atencion = models.ForeignKey(
        "catalogos.CatCentroAtencion", on_delete=models.PROTECT, db_column="id_centro_atencion", related_name="+",
    )
    clues = models.CharField(max_length=50)  # copia al crear
    # Paciente atendido (cns_paciente). Interno: nunca se expone en la API.
    paciente = models.ForeignKey(
        "consulta_medica.Patient", on_delete=models.PROTECT, db_column="id_paciente",
        related_name="+", null=True, blank=True,
    )
    id_usuario_solicitante = models.BigIntegerField()
    motivos = models.JSONField(default=list)
    modalidad = models.CharField(max_length=16, choices=Modalidad.choices)
    aprobaciones_requeridas = models.PositiveSmallIntegerField(default=1)
    estatus = models.CharField(max_length=12, choices=Estatus.choices, default=Estatus.PENDIENTE)
    prioridad = models.CharField(max_length=8, choices=Prioridad.choices, default=Prioridad.NORMAL)
    fecha_limite = models.DateTimeField()
    id_usuario_resolucion = models.BigIntegerField(null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    motivo_cierre = models.ForeignKey(
        Motivo, on_delete=models.PROTECT, db_column="id_motivo_cierre", related_name="+", null=True, blank=True,
    )
    descripcion_motivo_cierre = models.CharField(max_length=500, null=True, blank=True)
    # Datos minimos para evaluar (sin nombre ni diagnostico del paciente).
    resumen_minimo = models.JSONField(default=dict)
    # SHA-256 del contenido a autorizar: lo firma cada decision.
    hash_contenido = models.CharField(max_length=64)
    sin_elegibles = models.BooleanField(default=False)
    # Se escala una sola vez (F7): NULL = todavia no.
    fecha_escalamiento = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "aut_solicitud"
        constraints = [
            models.CheckConstraint(
                condition=Q(aprobaciones_requeridas__gte=1, aprobaciones_requeridas__lte=10),
                name="aut_solicitud_aprobaciones_ck",
            ),
            models.CheckConstraint(
                condition=~Q(modalidad="PRIMERO_VALIDO") | Q(aprobaciones_requeridas=1),
                name="aut_solicitud_modalidad_ck",
            ),
            # Autorizada o rechazada <=> tiene quien y cuando la resolvio.
            models.CheckConstraint(
                condition=(
                    Q(estatus__in=["AUTORIZADA", "RECHAZADA"])
                    & Q(id_usuario_resolucion__isnull=False, fecha_resolucion__isnull=False)
                )
                | (~Q(estatus__in=["AUTORIZADA", "RECHAZADA"]) & Q(id_usuario_resolucion__isnull=True)),
                name="aut_solicitud_resolucion_ck",
            ),
            models.CheckConstraint(
                condition=~Q(estatus="RECHAZADA") | Q(motivo_cierre__isnull=False),
                name="aut_solicitud_rechazo_motivo_ck",
            ),
            models.UniqueConstraint(
                fields=["tipo_origen", "id_origen"], condition=Q(estatus="PENDIENTE"),
                name="aut_solicitud_origen_pendiente_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["estatus", "tipo_autorizacion", "centro_atencion", "-fecha_creacion"],
                name="aut_solicitud_bandeja_idx",
            ),
            models.Index(fields=["fecha_limite"], condition=Q(estatus="PENDIENTE"), name="aut_solicitud_limite_idx"),
            models.Index(fields=["tipo_origen", "id_origen"], name="aut_solicitud_origen_idx"),
        ]


class SolicitudItem(models.Model):
    """Copia de lo que se autoriza. Al recalcular, los items anteriores quedan inactivos."""

    class TipoItem(models.TextChoices):
        MEDICAMENTO = "MEDICAMENTO", "Medicamento"
        ESTUDIO = "ESTUDIO", "Estudio"
        NOTA = "NOTA", "Nota"

    id_solicitud_item = models.BigAutoField(primary_key=True)
    solicitud = models.ForeignKey(Solicitud, on_delete=models.PROTECT, db_column="id_solicitud", related_name="items")
    tipo_item = models.CharField(max_length=12, choices=TipoItem.choices)
    id_item_origen = models.BigIntegerField()
    descripcion = models.CharField(max_length=255)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    motivo = models.CharField(max_length=24, null=True, blank=True)
    requiere_autorizacion = models.BooleanField(default=True)
    esta_activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "aut_solicitud_item"
        indexes = [models.Index(fields=["solicitud", "esta_activo"], name="aut_solicitud_item_idx")]


class SolicitudDestinatario(models.Model):
    class TipoSeleccion(models.TextChoices):
        ELEGIBLES = "ELEGIBLES", "Elegibles del tipo y centro"
        MANUAL = "MANUAL", "Seleccionado manualmente"
        ESPECIFICO = "ESPECIFICO", "Autorizador específico"
        ESCALAMIENTO = "ESCALAMIENTO", "Reenvío por escalamiento"
        DIRECTO = "DIRECTO", "Decidió sin haber sido notificado"

    class Estatus(models.TextChoices):
        NOTIFICADO = "NOTIFICADO", "Notificado"
        VISTO = "VISTO", "Visto"
        DECIDIO = "DECIDIO", "Decidió"
        ATENDIDA_POR_OTRO = "ATENDIDA_POR_OTRO", "Atendida por otro"
        INHABILITADO = "INHABILITADO", "Inhabilitado"
        RETIRADO = "RETIRADO", "Retirado"

    id_solicitud_destinatario = models.BigAutoField(primary_key=True)
    solicitud = models.ForeignKey(
        Solicitud, on_delete=models.PROTECT, db_column="id_solicitud", related_name="destinatarios",
    )
    autorizador = models.ForeignKey(
        Autorizador, on_delete=models.PROTECT, db_column="id_autorizador", related_name="solicitudes_recibidas",
    )
    tipo_seleccion = models.CharField(max_length=12, choices=TipoSeleccion.choices)
    # MULTIPLE: si hay obligatorios, la solicitud no se autoriza sin su aprobacion.
    es_obligatorio = models.BooleanField(default=False)
    estatus = models.CharField(max_length=20, choices=Estatus.choices, default=Estatus.NOTIFICADO)
    id_usuario_envio = models.BigIntegerField(null=True, blank=True)  # NULL = sistema
    fecha_envio = models.DateTimeField(auto_now_add=True)
    fecha_visto = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "aut_solicitud_destinatario"
        constraints = [
            models.UniqueConstraint(fields=["solicitud", "autorizador"], name="aut_solicitud_destinatario_uq"),
        ]
        indexes = [models.Index(fields=["autorizador", "estatus"], name="aut_sol_dest_autorizador_idx")]


class SolicitudDecision(models.Model):
    """Decision firmada. Solo insercion (trigger en PostgreSQL)."""

    class Decision(models.TextChoices):
        APROBAR = "APROBAR", "Aprobar"
        RECHAZAR = "RECHAZAR", "Rechazar"

    id_solicitud_decision = models.BigAutoField(primary_key=True)
    solicitud = models.ForeignKey(Solicitud, on_delete=models.PROTECT, db_column="id_solicitud", related_name="decisiones")
    autorizador = models.ForeignKey(Autorizador, on_delete=models.PROTECT, db_column="id_autorizador", related_name="+")
    usuario = models.ForeignKey(
        "authentication.SyUsuario", on_delete=models.PROTECT, db_column="id_usuario", related_name="+",
    )
    autorizador_tipo = models.ForeignKey(
        AutorizadorTipo, on_delete=models.PROTECT, db_column="id_autorizador_tipo", related_name="+",
    )
    alcance_aplicado = models.CharField(max_length=12)
    # Copia en texto: Usuarios borra y recrea cedulas al editar.
    numero_cedula = models.CharField(max_length=30, null=True, blank=True)
    decision = models.CharField(max_length=10, choices=Decision.choices)
    motivo = models.ForeignKey(Motivo, on_delete=models.PROTECT, db_column="id_motivo", related_name="+", null=True, blank=True)
    descripcion_motivo = models.CharField(max_length=500, null=True, blank=True)
    metodo_firma = models.CharField(max_length=10, choices=MetodoFirma.choices)
    hash_contenido = models.CharField(max_length=64)
    fecha_firma = models.DateTimeField()
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    agente_usuario = models.CharField(max_length=255, null=True, blank=True)
    identificador_peticion = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "aut_solicitud_decision"
        constraints = [
            # Una decision por autorizador sobre el MISMO contenido.
            models.UniqueConstraint(
                fields=["solicitud", "autorizador", "hash_contenido"], name="aut_solicitud_decision_uq",
            ),
            models.CheckConstraint(
                condition=~Q(decision="RECHAZAR") | Q(motivo__isnull=False),
                name="aut_solicitud_decision_rechazo_ck",
            ),
        ]


class SolicitudTransicion(models.Model):
    """Historial de estados. Solo insercion (trigger en PostgreSQL)."""

    id_solicitud_transicion = models.BigAutoField(primary_key=True)
    solicitud = models.ForeignKey(
        Solicitud, on_delete=models.PROTECT, db_column="id_solicitud", related_name="transiciones",
    )
    estatus_anterior = models.CharField(max_length=12, null=True, blank=True)
    estatus_nuevo = models.CharField(max_length=12)
    # CREADA, RECALCULADA, APROBACION_PARCIAL, AUTORIZADA, RECHAZADA, VENCIDA, CANCELADA_ORIGEN,
    # NOTIFICADA, ESCALADA
    evento = models.CharField(max_length=24)
    id_usuario = models.BigIntegerField(null=True, blank=True)  # NULL = proceso automatico
    fecha_evento = models.DateTimeField(auto_now_add=True)
    detalle = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "aut_solicitud_transicion"
        indexes = [models.Index(fields=["solicitud", "fecha_evento"], name="aut_sol_transicion_idx")]
