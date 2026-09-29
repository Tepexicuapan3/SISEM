from django.db import models


class SolicitudArco(models.Model):
    """
    Solicitud de derechos ARCO (Acceso, Rectificacion, Cancelacion,
    Oposicion) sobre los datos personales del expediente clinico -- Ley
    General de Proteccion de Datos Personales en Posesion de Sujetos
    Obligados (change `solicitudes-arco`, Fase 4 del plan NOM-024).

    El paciente se identifica por el par `(no_exp, pk_num)` como texto/entero
    plano, SIN FK: `CatEmpleado`/`CatFamiliar` viven en la base
    `expedientes` (ver `routers.ExpedientesRouter`) y no se puede cruzar una
    FK entre bases.

    `fecha_limite` se calcula al registrar la solicitud con
    `settings.ARCO_PLAZO_DIAS_HABILES` (default 20, PENDIENTE de confirmar
    con juridico) y NO se recalcula si el setting cambia despues: el plazo
    que cuenta es el vigente cuando se recibio la solicitud.

    Una solicitud resuelta (`procedente`/`improcedente`) es inmutable -- la
    trazabilidad de cada cambio de estatus vive en `AuditoriaEvento`
    (`recurso_tipo="solicitud_arco"`).
    """

    class Tipo(models.TextChoices):
        # Documento: A acceso, R rectificacion, C cancelacion, O oposicion.
        ACCESO = "A", "Acceso"
        RECTIFICACION = "R", "Rectificacion"
        CANCELACION = "C", "Cancelacion"
        OPOSICION = "O", "Oposicion"

    class Estatus(models.TextChoices):
        RECIBIDA = "recibida", "Recibida"
        EN_PROCESO = "en_proceso", "En proceso"
        PROCEDENTE = "procedente", "Procedente"
        IMPROCEDENTE = "improcedente", "Improcedente"

    ESTATUS_FINALES = (Estatus.PROCEDENTE, Estatus.IMPROCEDENTE)

    class Relacion(models.TextChoices):
        TITULAR = "titular", "Titular de los datos"
        REPRESENTANTE = "representante", "Representante legal"

    id_solicitud = models.BigAutoField(primary_key=True, db_column="id_solicitud")
    folio = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=1, choices=Tipo.choices)
    estatus = models.CharField(
        max_length=20, choices=Estatus.choices, default=Estatus.RECIBIDA, db_index=True,
    )
    no_exp = models.CharField(max_length=20, db_index=True)
    pk_num = models.IntegerField(default=0)
    solicitante_nombre = models.CharField(max_length=255)
    solicitante_relacion = models.CharField(
        max_length=20, choices=Relacion.choices, default=Relacion.TITULAR,
    )
    solicitante_correo = models.CharField(max_length=255, null=True, blank=True)
    solicitante_telefono = models.CharField(max_length=50, null=True, blank=True)
    descripcion = models.TextField()
    fecha_recepcion = models.DateField()
    fecha_limite = models.DateField(db_index=True)
    respuesta = models.TextField(null=True, blank=True)
    # Folio que asigna la Unidad de Transparencia del organismo a la
    # solicitud (documento "Historia Clinica Unificada", SOLICITUD_ARCO).
    folio_unidad_transparencia = models.CharField(max_length=50, null=True, blank=True)
    fch_resolucion = models.DateTimeField(null=True, blank=True)
    # SOLICITUD_ARCO.fe_respuesta (documento): fecha en que se respondio.
    fecha_respuesta = models.DateField(null=True, blank=True)
    registrada_por = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="registrada_por_id",
        null=True,
        on_delete=models.SET_NULL,
        related_name="solicitudes_arco_registradas",
    )
    resuelta_por = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="resuelta_por_id",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="solicitudes_arco_resueltas",
    )
    fch_alta = models.DateTimeField(auto_now_add=True)
    fch_modf = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "solicitudes_arco"
        managed = True
        ordering = ["-fch_alta"]
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="solicitudes_arco_paciente_idx"),
        ]

    def __str__(self):
        return self.folio

    @property
    def is_final(self):
        return self.estatus in self.ESTATUS_FINALES
