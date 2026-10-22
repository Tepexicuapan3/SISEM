import uuid as _uuid

from django.db import models


# ─── Citas ────────────────────────────────────────────────────────────────────

# Canal por el que una franja/cita está habilitada u origina. Mismos valores
# que apps.medicos.models.CANAL_ATENCION (no se importa entre apps para no
# acoplarlas; cada modelo define su propia copia, como ya hacen los demás
# choices de este archivo).
CANAL_CHOICES = [
    ("PRESENCIAL", "Presencial"),
    ("LINEA",      "En línea"),
    ("AMBOS",      "Ambos"),
]


class OrigenCanalCita(models.TextChoices):
    RECEPCION = "RECEPCION", "Recepción"
    PORTAL    = "PORTAL",    "Portal"


class EstatusCita(models.TextChoices):
    AGENDADA   = "agendada",   "Agendada"
    CONFIRMADA = "confirmada", "Confirmada"
    ATENDIDA   = "atendida",   "Atendida"
    CANCELADA  = "cancelada",  "Cancelada"
    NO_ASISTIO = "no_asistio", "No asistió"


class CitaMedica(models.Model):
    """
    Cita médica agendada.

    El folio se convierte en ``appointment_id`` de ``Visit`` cuando el paciente
    realiza el check-in en recepción.
    """

    folio        = models.CharField(max_length=32, unique=True)

    # Paciente (núcleo familiar — mismo esquema que rcp_visits)
    no_exp       = models.CharField(max_length=20, db_index=True)
    # IntegerField, no smallint: los PK_NUM de SERMED pasan de 32 767 (p. ej.
    # 48411) y en Postgres la cita fallaba con "smallint out of range". Mismo
    # arreglo que rcp_visits (recepcion.0006).
    pk_num       = models.IntegerField(default=0)

    # Médico y consultorio
    medico       = models.ForeignKey(
        "medicos.CatMedico",
        db_column="medico_id",
        on_delete=models.PROTECT,
        related_name="citas",
    )
    consultorio  = models.ForeignKey(
        "catalogos.Consultorios",
        db_column="consultorio_id",
        db_constraint=False,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="citas",
    )

    # Fecha y duración
    fecha_hora   = models.DateTimeField(db_index=True)
    duracion_min = models.SmallIntegerField(default=20)

    # Tipo de servicio
    servicio_tipo = models.CharField(
        max_length=32,
        choices=[
            ("medicina_general", "Medicina general"),
            ("especialidad",     "Especialidad"),
            ("urgencias",        "Urgencias"),
        ],
        default="medicina_general",
    )

    # Estado
    estatus = models.CharField(
        max_length=20,
        choices=EstatusCita.choices,
        default=EstatusCita.AGENDADA,
        db_index=True,
    )

    # Datos adicionales
    motivo     = models.CharField(max_length=255, null=True, blank=True)
    notas      = models.TextField(null=True, blank=True)

    # Portal en línea
    origen_canal = models.CharField(
        max_length=20,
        choices=OrigenCanalCita.choices,
        default=OrigenCanalCita.RECEPCION,
    )
    verificado_en       = models.DateTimeField(null=True, blank=True)
    # Igual que created_by_id: id plano de usuario, sin FK real (mismo patrón
    # de auditoría ya usado en este modelo y en el resto del proyecto).
    verificado_por_id   = models.BigIntegerField(null=True, blank=True)
    cancelado_en        = models.DateTimeField(null=True, blank=True)
    cancelado_por_id    = models.BigIntegerField(null=True, blank=True)
    # Motivo tipificado (catálogo) — reemplaza el TextField libre original,
    # que se preserva como `motivo_detalle` para no perder datos existentes
    # (ver migración 0024, RenameField + AddField, nunca RemoveField+AddField
    # con el mismo nombre).
    motivo_cancelacion = models.ForeignKey(
        "catalogos.MotivoCita",
        db_column="motivo_cancelacion_id",
        db_constraint=False,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="citas_canceladas",
    )
    # Texto libre complementario/opcional al motivo tipificado de arriba.
    motivo_detalle      = models.TextField(null=True, blank=True)

    # Auditoría
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    created_by_id   = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "citas_medicas"
        indexes  = [
            models.Index(fields=["medico", "fecha_hora"],            name="citas_medico_fechahora_idx"),
            models.Index(fields=["no_exp", "pk_num"],                name="citas_noexp_pknum_idx"),
            models.Index(fields=["estatus", "fecha_hora"],           name="citas_estatus_fechahora_idx"),
            models.Index(fields=["consultorio"],                     name="citas_consultorio_idx"),
            models.Index(fields=["medico", "estatus", "fecha_hora"], name="citas_medico_estatus_fecha_idx"),
        ]

    def __str__(self):
        return f"Cita {self.folio} — {self.no_exp}/{self.pk_num} ({self.estatus})"

    @staticmethod
    def generar_folio() -> str:
        return f"CIT-{_uuid.uuid4().hex[:10].upper()}"


class HorarioDisponible(models.Model):
    """
    Slot de tiempo disponible para un médico en un consultorio.
    Se genera automáticamente cada semana mediante la tarea Celery.
    """

    medico      = models.ForeignKey(
        "medicos.CatMedico",
        on_delete=models.CASCADE,
        related_name="slots",
    )
    consultorio = models.ForeignKey(
        "catalogos.Consultorios",
        db_constraint=False,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    fecha        = models.DateField(db_index=True)
    hora         = models.TimeField()
    duracion_min = models.SmallIntegerField(default=20)
    disponible   = models.BooleanField(default=True, db_index=True)
    # Se copia desde RelMedicoConsultorioHorario.canal al generar el slot
    # (la lógica de copia es de una fase posterior). Default "PRESENCIAL"
    # preserva el comportamiento actual.
    canal        = models.CharField(max_length=10, choices=CANAL_CHOICES, default="PRESENCIAL")
    cita         = models.OneToOneField(
        CitaMedica,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slot",
    )
    # Ausencia del médico que dejó este horario sin habilitar
    # (disponible=False). Al borrar la ausencia se rehabilitan solo los
    # horarios que ella bloqueó (ver services/bloqueo_slots_service.py).
    bloqueado_por_excepcion = models.ForeignKey(
        "medicos.RelMedicoExcepcion",
        db_column="id_excepcion_bloqueo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slots_bloqueados",
    )

    class Meta:
        db_table      = "citas_horarios_disponibles"
        unique_together = [("medico", "fecha", "hora")]
        indexes = [
            # Soporta el filtro de slots por consultorio (Fase 3) y la
            # agregación mensual de disponibilidad (Fase 4): consultorio
            # (igualdad) -> fecha (rango, vía fecha__range) -> canal
            # (igualdad). El orden importa: el rango va último entre las
            # columnas usadas para seek.
            models.Index(fields=["consultorio", "fecha", "canal"], name="hd_consult_fecha_canal_idx"),
        ]


class CitaNotificacion(models.Model):
    """Registro de correos enviados para una cita (confirmación, recordatorio)."""

    TIPO_CHOICES = [
        ("confirmacion", "Confirmación"),
        ("recordatorio", "Recordatorio"),
        ("comprobante_portal", "Comprobante portal"),
        ("cancelacion", "Cancelación"),
    ]

    cita          = models.ForeignKey(CitaMedica, on_delete=models.CASCADE, related_name="notificaciones")
    tipo          = models.CharField(max_length=20, choices=TIPO_CHOICES)
    enviado       = models.BooleanField(default=False)
    email_destino = models.EmailField(null=True, blank=True)
    enviado_at    = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "citas_notificaciones"


# ─── Visit ────────────────────────────────────────────────────────────────────

class Visit(models.Model):
    class ArrivalType(models.TextChoices):
        APPOINTMENT = "appointment", "appointment"
        WALK_IN = "walk_in", "walk_in"

    class ServiceType(models.TextChoices):
        MEDICINA_GENERAL = "medicina_general", "medicina_general"
        ESPECIALIDAD = "especialidad", "especialidad"
        URGENCIAS = "urgencias", "urgencias"

    id_visit = models.BigAutoField(primary_key=True, db_column="id_visit")
    # unique=True ya crea indice, no hace falta db_index=True
    folio = models.CharField(max_length=32, db_column="folio", unique=True)
    # Identificación del paciente: expediente del titular + número de miembro familiar.
    # pk_num = 0 → el propio trabajador (titular).
    # pk_num > 0 → derechohabiente (cat_familiar.pk_num).
    no_exp     = models.CharField(max_length=20, db_column="no_exp", db_index=True, null=True, blank=True)
    pk_num     = models.IntegerField(db_column="pk_num", default=0)
    arrival_type = models.CharField(
        max_length=16,
        choices=ArrivalType.choices,
        db_column="arrival_type",
    )
    service_type = models.CharField(
        max_length=32,
        choices=ServiceType.choices,
        db_column="service_type",
        default=ServiceType.MEDICINA_GENERAL,
    )
    appointment_id = models.CharField(
        max_length=64,
        db_column="appointment_id",
        null=True,
        blank=True,
    )
    # correcto para filtro doctorId
    doctor = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="doctor_id",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitas_atendidas",
    )
    # Consultorio asignado en el check-in (FK a cat_consultorios.id_consult).
    consultorio = models.ForeignKey(
        "catalogos.Consultorios",
        db_column="consultorio_id",
        db_constraint=False,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitas",
    )
    # Tipo de cita seleccionado en el check-in (FK a cat_tpcitas.id_tpcita).
    # Mismo patron que `consultorio`: sin constraint fisica, se valida
    # existencia (no is_active) en CreateVisitSerializer.validate_tipoCitaId.
    tipo_cita = models.ForeignKey(
        "catalogos.TipoDeCitas",
        db_column="tipo_cita_id",
        db_constraint=False,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitas",
    )
    # Nombre del paciente capturado en el check-in (desnormalizado para la ficha).
    nombre_paciente = models.CharField(
        max_length=255,
        db_column="nombre_paciente",
        null=True,
        blank=True,
    )
    notes = models.CharField(
        max_length=255,
        db_column="notes",
        null=True,
        blank=True,
    )
    hora_consulta  = models.TimeField(db_column="hora_consulta", null=True, blank=True)
    fecha_consulta = models.DateField(db_column="fecha_consulta", null=True, blank=True)
    # Número secuencial de ficha dentro del turno del día — asignado al crear la visita
    num_ficha     = models.PositiveSmallIntegerField(db_column="num_ficha", null=True, blank=True)
    # Nombre del turno al momento de la creación (inmutable para historial)
    turno_nombre  = models.CharField(db_column="turno_nombre", max_length=50, null=True, blank=True)
    # dejamos db_index en el campo y quitamos el indice duplicado en Meta
    status = models.CharField(max_length=32, db_column="status", db_index=True)
    fch_alta = models.DateTimeField(auto_now_add=True, db_column="fch_alta")
    fch_modf = models.DateTimeField(auto_now=True, db_column="fch_modf")
    # baja logica: null cuando sigue activa
    fch_baja = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    # id del usuario de recepción que registró la visita
    created_by_id = models.BigIntegerField(db_column="created_by_id", null=True, blank=True)
    # Motivo tipificado (catálogo) capturado al cancelar la visita (mismo
    # patron que CitaMedica.motivo_cancelacion). Solo se llena en la
    # transicion en_espera -> cancelada, exigida por
    # VisitStatusView/change_visit_status. El TextField libre original se
    # preserva como `motivo_detalle` (RenameField, no se pierden datos).
    motivo_cancelacion = models.ForeignKey(
        "catalogos.MotivoCita",
        db_column="motivo_cancelacion_id",
        db_constraint=False,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitas_canceladas",
    )
    # Texto libre complementario/opcional al motivo tipificado de arriba.
    motivo_detalle = models.TextField(null=True, blank=True)
    # Motivo u oficio de Capital Humano para atender a un paciente sin
    # vigencia (check-in de cita). Quién lo aceptó = created_by_id. Null
    # cuando el paciente tenía vigencia.
    autorizacion_vigencia = models.TextField(
        db_column="autorizacion_vigencia", null=True, blank=True,
    )

    class Meta:
        db_table = "rcp_visits"
        indexes = [
            models.Index(fields=["doctor", "status"], name="rcp_visits_doc_status_idx"),
            models.Index(fields=["fch_alta"], name="rcp_visits_fch_alta_idx"),
            # Soporta el lookup de "signos vitales de hoy" por integrante
            # familiar (join VisitVitalSigns -> Visit filtrando por
            # no_exp+pk_num) usado por el reuso mismo dia (Fase 2).
            models.Index(fields=["no_exp", "pk_num"], name="rcp_visits_noexp_pknum_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                name="rcp_visits_arrival_appointment_ck",
                condition=(
                    (
                        models.Q(arrival_type="appointment")
                        & models.Q(appointment_id__isnull=False)
                        & ~models.Q(appointment_id="")
                    )
                    | (
                        models.Q(arrival_type="walk_in")
                        & (models.Q(appointment_id__isnull=True) | models.Q(appointment_id=""))
                    )
                ),
            ),
        ]


# ─── Turno de fichas ──────────────────────────────────────────────────────────

class TurnoFichaConfig(models.Model):
    """
    Configura los turnos de atención y cuántas fichas se entregan por turno.
    El num_ficha del PDF se calcula contando las visitas del turno en el día.
    """

    nombre       = models.CharField(max_length=50, db_column="nombre", unique=True)
    hora_inicio  = models.TimeField(db_column="hora_inicio")
    hora_fin     = models.TimeField(db_column="hora_fin")
    max_fichas   = models.PositiveSmallIntegerField(db_column="max_fichas", default=18)
    is_active    = models.BooleanField(db_column="is_active", default=True)

    class Meta:
        db_table = "rcp_turno_ficha_config"
        ordering = ["hora_inicio"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.hora_inicio}–{self.hora_fin}, max {self.max_fichas})"


# ─── Auditoría de estatus (NOM-024-SSA3-2012) ─────────────────────────────────

class VisitStatusLog(models.Model):
    """
    Registro inmutable de cada cambio de estado de una visita.
    Requerido por NOM-024-SSA3-2012 para trazabilidad clínica.
    """

    visit         = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name="status_logs",
        db_column="visit_id",
    )
    from_status   = models.CharField(max_length=32, null=True, blank=True, db_column="from_status")
    to_status     = models.CharField(max_length=32, db_column="to_status")
    changed_by_id = models.BigIntegerField(null=True, blank=True, db_column="changed_by_id")
    changed_at    = models.DateTimeField(auto_now_add=True, db_column="changed_at")
    notes         = models.CharField(max_length=255, null=True, blank=True, db_column="notes")

    class Meta:
        db_table = "rcp_visit_status_log"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"Visit {self.visit_id}: {self.from_status} → {self.to_status}"


class CitaEstatusLog(models.Model):
    """
    Registro inmutable de cada cambio de estado de una cita agendada.
    Mismo patrón que VisitStatusLog — requerido por NOM-024-SSA3-2012.
    Cubre el tramo AGENDADA→...→(confirmada/atendida/cancelada/no_asistio)
    que ocurre antes de que la cita se convierta en Visit (check-in).
    """

    cita          = models.ForeignKey(
        CitaMedica,
        on_delete=models.CASCADE,
        related_name="estatus_logs",
        db_column="cita_id",
    )
    from_status   = models.CharField(max_length=20, null=True, blank=True, db_column="from_status")
    to_status     = models.CharField(max_length=20, db_column="to_status")
    changed_by_id = models.BigIntegerField(null=True, blank=True, db_column="changed_by_id")
    changed_at    = models.DateTimeField(auto_now_add=True, db_column="changed_at")
    notes         = models.CharField(max_length=255, null=True, blank=True, db_column="notes")

    class Meta:
        db_table = "citas_estatus_log"
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"Cita {self.cita_id}: {self.from_status} → {self.to_status}"
