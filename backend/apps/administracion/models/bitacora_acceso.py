from django.db import models


class BitacoraAcceso(models.Model):
    """
    BITACORA_ACCESO (documento "Historia Clinica Unificada", controles de
    datos sensibles): quien vio, imprimio, exporto o modifico la historia de
    cada paciente -- no solo los cambios.

    Tabla propia y append-only (nunca se edita ni se borra desde la app).
    `no_exp`/`tp_paciente` son NULL solo en exportaciones de reportes que
    abarcan a muchos pacientes (el documento pide registrar TODA exportacion).
    `restringidos` > 0 = la respuesta ocultó diagnosticos sensibles (VIH,
    salud mental, sustancias) porque el usuario no tenia el permiso.
    """

    class Accion(models.TextChoices):
        VER = "ver", "Ver"
        IMPRIMIR = "imprimir", "Imprimir"
        EXPORTAR = "exportar", "Exportar"
        MODIFICAR = "modificar", "Modificar"

    id = models.BigAutoField(primary_key=True, db_column="id")
    no_exp = models.CharField(max_length=20, null=True, blank=True)
    tp_paciente = models.IntegerField(null=True, blank=True)
    usuario = models.ForeignKey(
        "authentication.SyUsuario",
        db_column="id_usuario",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # BITACORA_ACCESO.cd_usuario: el login al momento del acceso (se conserva
    # aunque el usuario cambie de nombre o se de de baja).
    cd_usuario = models.CharField(max_length=50, null=True, blank=True)
    recurso = models.CharField(max_length=40)
    accion = models.CharField(max_length=10, choices=Accion.choices)
    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    endpoint = models.CharField(max_length=255, null=True, blank=True)
    restringidos = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "bitacora_acceso"
        managed = True
        ordering = ["-fecha_hora", "-id"]
        indexes = [
            models.Index(fields=["no_exp", "tp_paciente"], name="bitacora_acceso_paciente_idx"),
            models.Index(fields=["accion", "fecha_hora"], name="bitacora_acceso_accion_idx"),
        ]
