import json
import uuid

from django.db import models


# ─── CONSTANTES ─────────────────────────────────────────────────────────────

TIPO_MEDICO = [
    ("CLINICA",  "Clínica"),
    ("HOSPITAL", "Hospital"),
    ("AMBOS",    "Ambos"),
]

ESTATUS_MEDICO = [
    ("ACTIVO",       "Activo"),
    ("VACACIONES",   "Vacaciones"),
    ("INCAPACIDAD",  "Incapacidad"),
    ("SUSPENDIDO",   "Suspendido"),
    ("BAJA",         "Baja"),
]

DIAS_SEMANA = [
    ("LUNES",     "Lunes"),
    ("MARTES",    "Martes"),
    ("MIERCOLES", "Miércoles"),
    ("JUEVES",    "Jueves"),
    ("VIERNES",   "Viernes"),
    ("SABADO",    "Sábado"),
    ("DOMINGO",   "Domingo"),
]

TIPO_EXCEPCION = [
    ("VACACIONES",      "Vacaciones"),
    ("INCAPACIDAD",     "Incapacidad"),
    ("PERMISO",         "Permiso"),
    ("HORA_COMIDA",     "Hora de comida"),
    ("CAPACITACION",    "Capacitación"),
    ("AUSENCIA",        "Ausencia"),
    ("SUSPENSION",      "Suspensión"),
    ("CAMBIO_HORARIO",  "Cambio de horario"),
]

TIPO_ADSCRIPCION = [
    ("DEFINITIVA", "Definitiva"),
    ("TEMPORAL",   "Temporal"),
]

CANAL_ATENCION = [
    ("PRESENCIAL", "Presencial"),
    ("LINEA",      "En línea"),
    ("AMBOS",      "Ambos"),
]

TIPO_ASIGNACION = [
    ("PERMANENTE", "Permanente"),
    ("TEMPORAL",   "Temporal"),
]

MOTIVO_COBERTURA = [
    ("VACACIONES",  "Vacaciones"),
    ("INCAPACIDAD", "Incapacidad"),
    ("PERMISO",     "Permiso"),
    ("OTRO",        "Otro"),
]


# ─── CATÁLOGO MÉDICOS ────────────────────────────────────────────────────────

class CatMedico(models.Model):
    """
    Perfil médico especializado. Solo datos que usuarios no almacena.

    PK propia (`id`), independiente de `id_usuario` desde el cambio
    `medico-pk-independiente` (ver Engram, topic_key
    sdd/medico-pk-independiente/design). Desde `medicos-id-no-medico`,
    `id` ES el "No. Médico" del legado (el import lo inserta explícito y
    ajusta la secuencia). `id_usuario` bajó a FK nullable
    (`SET_NULL`): un médico puede existir sin cuenta de usuario del sistema
    (médico externo/invitado). Esquema físico realizado en
    `medicos/migrations/0004_expand_surrogate_pk.py` .. `0007_switch_surrogate_pk.py`.
    """

    id_usuario = models.OneToOneField(
        "authentication.SyUsuario",
        db_column="id_usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medico",
    )
    # Datos personales: SOLO para médicos SIN usuario (los que entran por el
    # import Excel). Con usuario, la fuente de verdad es DetUsuario /
    # DetUsuarioCedula; el CheckConstraint de Meta lo garantiza. Lectura
    # única vía apps.medicos.identity (display_name / nombre_partes /
    # cedula_profesional). cedula_profesional=30 igual que
    # DetUsuarioCedula.numero, para moverla al asignar usuario sin truncar.
    nombre             = models.CharField(max_length=80, null=True, blank=True)
    paterno            = models.CharField(max_length=80, null=True, blank=True)
    materno            = models.CharField(max_length=80, null=True, blank=True)
    cedula_profesional = models.CharField(max_length=30, null=True, blank=True)
    # Escuela de egreso, igual que DetUsuario.id_escuela (misma regla: solo
    # sin usuario; al asignar usuario se mueve a DetUsuario si está vacía).
    id_escuela = models.ForeignKey(
        "catalogos.Escuelas",
        db_column="id_escuela",
        db_constraint=False,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    tipo_medico   = models.CharField(max_length=10, choices=TIPO_MEDICO, default="CLINICA")
    servicio        = models.CharField(max_length=100, null=True, blank=True)
    observaciones   = models.TextField(null=True, blank=True)
    estatus_medico  = models.CharField(max_length=20, choices=ESTATUS_MEDICO, default="ACTIVO", db_index=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(null=True, blank=True)
    created_by_id   = models.BigIntegerField(null=True, blank=True)
    updated_by_id   = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "cat_medicos"
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(id_usuario__isnull=True)
                    | models.Q(
                        nombre__isnull=True,
                        paterno__isnull=True,
                        materno__isnull=True,
                        cedula_profesional__isnull=True,
                        id_escuela__isnull=True,
                    )
                ),
                name="cat_medicos_datos_personales_solo_sin_usuario",
            ),
        ]

    def __str__(self):
        return f"Médico #{self.id}"


# ─── ESPECIALIDADES ──────────────────────────────────────────────────────────

class RelMedicoEspecialidad(models.Model):
    medico          = models.ForeignKey(CatMedico, on_delete=models.CASCADE, related_name="especialidades")
    especialidad    = models.ForeignKey("catalogos.Especialidades", on_delete=models.PROTECT, db_constraint=False)
    es_principal    = models.BooleanField(default=False)

    class Meta:
        db_table = "rel_medico_especialidad"
        unique_together = [("medico", "especialidad")]

    def __str__(self):
        return f"{self.medico_id} - {self.especialidad_id}"


# ─── CENTROS ─────────────────────────────────────────────────────────────────

class RelMedicoCentro(models.Model):
    medico           = models.ForeignKey(CatMedico, on_delete=models.CASCADE, related_name="centros")
    centro           = models.ForeignKey("catalogos.CatCentroAtencion", on_delete=models.PROTECT)
    tipo_adscripcion = models.CharField(max_length=10, choices=TIPO_ADSCRIPCION, default="DEFINITIVA")
    fecha_inicio     = models.DateField()
    fecha_fin        = models.DateField(null=True, blank=True)
    is_active        = models.BooleanField(default=True, db_index=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    created_by_id    = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "rel_medico_centro"
        unique_together = [("medico", "centro", "fecha_inicio")]

    def __str__(self):
        return f"{self.medico_id} - Centro {self.centro_id}"


# ─── CONSULTORIOS ────────────────────────────────────────────────────────────

class RelMedicoConsultorio(models.Model):
    medico           = models.ForeignKey(CatMedico, on_delete=models.CASCADE, related_name="consultorios")
    consultorio      = models.ForeignKey("catalogos.Consultorios", on_delete=models.PROTECT, db_constraint=False)
    tipo_asignacion  = models.CharField(max_length=10, choices=TIPO_ASIGNACION, default="PERMANENTE")
    fecha_inicio     = models.DateField()
    fecha_fin        = models.DateField(null=True, blank=True)
    is_active        = models.BooleanField(default=True, db_index=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    created_by_id    = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "rel_medico_consultorio"

    def __str__(self):
        return f"{self.medico_id} - Consultorio {self.consultorio_id}"


# ─── HORARIO POR DÍA ─────────────────────────────────────────────────────────

class RelMedicoConsultorioHorario(models.Model):
    rel_medico_consultorio = models.ForeignKey(
        RelMedicoConsultorio,
        on_delete=models.CASCADE,
        related_name="horarios",
    )
    dia_semana          = models.CharField(max_length=10, choices=DIAS_SEMANA)
    hora_inicio         = models.TimeField()
    hora_fin            = models.TimeField()
    intervalo_cita_min  = models.SmallIntegerField(default=20)
    # Canal por el que esta franja está habilitada. Default "PRESENCIAL" preserva
    # el comportamiento actual: ninguna franja existente queda expuesta al portal
    # hasta que alguien la marque explícitamente como LINEA/AMBOS.
    canal               = models.CharField(max_length=10, choices=CANAL_ATENCION, default="PRESENCIAL")

    class Meta:
        db_table = "rel_medico_consultorio_horario"
        unique_together = [("rel_medico_consultorio", "dia_semana", "hora_inicio")]

    def __str__(self):
        return f"{self.rel_medico_consultorio_id} {self.dia_semana} {self.hora_inicio}"


# ─── EXCEPCIONES ─────────────────────────────────────────────────────────────

class RelMedicoExcepcion(models.Model):
    medico          = models.ForeignKey(CatMedico, on_delete=models.CASCADE, related_name="excepciones")
    tipo            = models.CharField(max_length=20, choices=TIPO_EXCEPCION, db_index=True)
    fecha_inicio    = models.DateField(db_index=True)
    fecha_fin       = models.DateField()
    hora_inicio     = models.TimeField(null=True, blank=True)  # NULL = día completo
    hora_fin        = models.TimeField(null=True, blank=True)
    consultorio     = models.ForeignKey("catalogos.Consultorios", on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    motivo          = models.CharField(max_length=255, null=True, blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    created_by_id   = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "rel_medico_excepcion"
        indexes = [
            models.Index(fields=["medico", "fecha_inicio", "fecha_fin"]),
        ]

    def __str__(self):
        return f"{self.medico_id} {self.tipo} {self.fecha_inicio}"


# ─── COBERTURAS ──────────────────────────────────────────────────────────────

class RelMedicoCobertura(models.Model):
    medico_suplente = models.ForeignKey(CatMedico, on_delete=models.CASCADE, related_name="coberturas_como_suplente")
    medico_titular  = models.ForeignKey(CatMedico, on_delete=models.CASCADE, related_name="coberturas_como_titular")
    consultorio     = models.ForeignKey("catalogos.Consultorios", on_delete=models.PROTECT, db_constraint=False)
    centro          = models.ForeignKey("catalogos.CatCentroAtencion", on_delete=models.PROTECT)
    fecha_inicio    = models.DateField(db_index=True)
    fecha_fin       = models.DateField()
    motivo          = models.CharField(max_length=20, choices=MOTIVO_COBERTURA)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    created_by_id   = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "rel_medico_cobertura"
        indexes = [
            models.Index(fields=["medico_suplente", "fecha_inicio", "fecha_fin"]),
            models.Index(fields=["medico_titular", "fecha_inicio", "fecha_fin"]),
        ]

    def __str__(self):
        return f"Suplente {self.medico_suplente_id} cubre a {self.medico_titular_id}"


class RelMedicoCoberturaHorario(models.Model):
    cobertura   = models.ForeignKey(RelMedicoCobertura, on_delete=models.CASCADE, related_name="horarios")
    dia_semana  = models.CharField(max_length=10, choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin    = models.TimeField()

    class Meta:
        db_table = "rel_medico_cobertura_horario"

    def __str__(self):
        return f"Cobertura {self.cobertura_id} {self.dia_semana}"


# ─── IMPORT MASIVO EN SEGUNDO PLANO ──────────────────────────────────────────

class MedicoImportJob(models.Model):
    """
    Import masivo de médicos por Excel ejecutado en segundo plano (Celery).
    Calca `apps.administracion.models.UserImportJob`: el confirm síncrono no
    escala (~2700 médicos exceden el timeout HTTP: frontend 30 s, nginx 60 s).
    El confirm solo guarda el archivo aquí y encola
    `apps.medicos.tasks.procesar_import_medicos`; el frontend consulta
    `GET /medicos/import/jobs/<id>`.

    El archivo vive en la BD (`file_content`) porque `celery-worker` no
    comparte volumen con `backend`; se vacía al terminar. `result_json` es
    TEXT con JSON a mano (no `JSONField`): en la Postgres real hay columnas
    `json` (no `jsonb`) que rompen la lectura por ORM.

    El avance de la fase SAVING corre DENTRO de la transacción del lote, así
    que no puede escribirse aquí (no sería visible hasta el commit): va a la
    cache (Redis, compartida backend/worker) y la vista de estado lo combina.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "En cola"
        RUNNING = "RUNNING", "En proceso"
        SUCCESS = "SUCCESS", "Completado"
        VALIDATION_FAILED = "VALIDATION_FAILED", "Con errores de validacion"
        ERROR = "ERROR", "Error"

    class Phase(models.TextChoices):
        QUEUED = "QUEUED", "En cola"
        VALIDATING = "VALIDATING", "Validando archivo"
        SAVING = "SAVING", "Guardando médicos"
        DONE = "DONE", "Terminado"

    STATUS_FINALES = (Status.SUCCESS, Status.VALIDATION_FAILED, Status.ERROR)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="actor_id",
        null=True,
        on_delete=models.SET_NULL,
        related_name="medico_import_jobs",
    )
    file_name = models.CharField(max_length=255)
    file_content = models.BinaryField(null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True,
    )
    phase = models.CharField(max_length=20, choices=Phase.choices, default=Phase.QUEUED)
    total_records = models.IntegerField(default=0)
    processed = models.IntegerField(default=0)
    phase_total = models.IntegerField(default=0)
    inserted = models.IntegerField(default=0)
    result_json = models.TextField(null=True, blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    fch_alta = models.DateTimeField(auto_now_add=True)
    fch_inicio = models.DateTimeField(null=True, blank=True)
    fch_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "medico_import_jobs"
        ordering = ["-fch_alta"]

    def __str__(self):
        return f"{self.file_name} ({self.status})"

    @property
    def is_final(self):
        return self.status in self.STATUS_FINALES

    def get_result(self):
        return json.loads(self.result_json) if self.result_json else None

    def set_result(self, value):
        self.result_json = json.dumps(value, default=str, ensure_ascii=False)
