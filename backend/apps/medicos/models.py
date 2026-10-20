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
    `medico-pk-independiente`. Desde `medicos-legado-archivo`, todo médico
    tiene usuario: `id_usuario` es OneToOne NOT NULL con `PROTECT` (no se
    puede borrar un usuario que es médico) y la identidad (nombre, cédula,
    escuela, sexo, fecha de nacimiento) vive SOLO en DetUsuario /
    DetUsuarioCedula; se lee vía `apps.medicos.identity`. El catálogo del
    SISEM legado quedó archivado aparte en `LegacyMedico` (solo lectura) y
    ningún código legado se interpreta como `id`.
    """

    id_usuario = models.OneToOneField(
        "authentication.SyUsuario",
        db_column="id_usuario",
        on_delete=models.PROTECT,
        related_name="medico",
    )
    tipo_medico  = models.CharField(max_length=10, choices=TIPO_MEDICO, default="CLINICA")
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


# ─── ARCHIVO DEL CATÁLOGO LEGADO ─────────────────────────────────────────────

class LegacyMedico(models.Model):
    """
    Archivo de SOLO LECTURA de `cat_medicos` del SISEM legado (MySQL).

    Se carga por SQL (INSERT ... SELECT) a mano; SIRES no escribe aquí. Las
    columnas espejan los nombres del legado para que esa carga sea directa.
    Incluye a propósito filas que no son personas (clínicas/institutos): es un
    archivo fiel, no un catálogo depurado.

    REGLA DE ORO: un código legado nunca se interpreta como un id de SIRES.
    `no_medico` / `cd_medico` solo se usan para buscar en esta tabla;
    `medico_actual` es el único puente (N:1) hacia el médico vigente en SIRES.
    """

    no_medico = models.IntegerField(primary_key=True)
    cd_medico = models.CharField(max_length=10)  # clave RH (puede repetirse)
    ds_paterno = models.CharField(max_length=45, null=True, blank=True)
    ds_materno = models.CharField(max_length=45, null=True, blank=True)
    ds_nombre = models.CharField(max_length=45, null=True, blank=True)
    cd_sexo = models.CharField(max_length=1, null=True, blank=True)
    fe_nac = models.DateField(null=True, blank=True)
    no_cedula = models.CharField(max_length=20, null=True, blank=True)
    cd_clinica = models.IntegerField(null=True, blank=True)
    ds_clinica = models.CharField(max_length=150, null=True, blank=True)
    cd_especialidad = models.IntegerField(null=True, blank=True)
    ds_especialidad = models.CharField(max_length=150, null=True, blank=True)
    sw_status = models.CharField(max_length=1)
    cd_usuario = models.CharField(max_length=10, null=True, blank=True)
    medico_actual = models.ForeignKey(
        CatMedico,
        db_column="id_medico_actual",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registros_legado",
    )
    fch_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "legacy_medico"
        verbose_name = "Médico legado"
        verbose_name_plural = "Médicos legado"
        indexes = [
            models.Index(fields=["cd_medico"], name="legacy_medico_cd_medico_idx"),
            models.Index(fields=["no_cedula"], name="legacy_medico_no_cedula_idx"),
        ]

    def __str__(self):
        return f"Legado #{self.no_medico}"


# ─── MÉDICOS EXTERNOS ────────────────────────────────────────────────────────

class MedicoExterno(models.Model):
    """
    Profesional de salud externo (IMSS, alta manual, etc.). Solo la tabla; sin
    endpoints ni UI todavía. Minimización de datos: sin fecha de nacimiento,
    sexo ni escuela.
    """

    origen = models.CharField(max_length=20)  # IMSS, MANUAL, ...
    id_externo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=80)
    paterno = models.CharField(max_length=80, null=True, blank=True)
    materno = models.CharField(max_length=80, null=True, blank=True)
    cedula_profesional = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    institucion = models.CharField(max_length=150, null=True, blank=True)
    especialidad_texto = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medico_externo"
        verbose_name = "Médico externo"
        verbose_name_plural = "Médicos externos"
        constraints = [
            models.UniqueConstraint(
                fields=["origen", "id_externo"], name="medico_externo_origen_id_externo_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.origen}:{self.id_externo}"
