import json
import uuid

from django.db import models


class UserImportJob(models.Model):
    """
    Import masivo de usuarios por Excel ejecutado en segundo plano (Celery).

    Existe porque el confirm sincrono no escala: cada alta hashea la
    contrasena temporal con PBKDF2 (~0.5 s) y un lote de miles de filas
    excede cualquier timeout HTTP (frontend 30 s, nginx 60 s). El confirm
    ahora solo guarda el archivo aqui y encola
    `apps.administracion.tasks.procesar_import_usuarios`; el frontend
    consulta el avance por `GET /users/import/jobs/<id>`.

    El archivo se guarda en la BD (`file_content`) y no en disco porque el
    contenedor `celery-worker` no comparte volumen con `backend`. Se vacia al
    terminar el job.

    `result_json` es TEXT con JSON serializado a mano (no `JSONField`): en la
    Postgres real hay columnas `json` (no `jsonb`) que rompen la lectura por
    ORM -- asi se evita la duda por completo.
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
        PREPARING = "PREPARING", "Generando credenciales"
        SAVING = "SAVING", "Guardando usuarios"
        SENDING_EMAILS = "SENDING_EMAILS", "Enviando correos"
        DONE = "DONE", "Terminado"

    STATUS_FINALES = (Status.SUCCESS, Status.VALIDATION_FAILED, Status.ERROR)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="actor_id",
        null=True,
        on_delete=models.SET_NULL,
        related_name="user_import_jobs",
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
        db_table = "user_import_jobs"
        managed = True
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
