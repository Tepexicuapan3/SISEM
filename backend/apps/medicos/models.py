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
    sdd/medico-pk-independiente/design). `id_usuario` bajó a FK nullable
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
    # Nombre a mostrar cuando id_usuario es NULL (médico sin usuario) y no
    # hay DetUsuario del que tomar nombre_completo. Ver
    # apps.medicos.identity.display_name() para la cadena de fallback
    # completa (cierre de R5, propuesta obs #467).
    nombre_display  = models.CharField(max_length=200, null=True, blank=True)
    tipo_medico     = models.CharField(max_length=10, choices=TIPO_MEDICO, default="CLINICA")
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
