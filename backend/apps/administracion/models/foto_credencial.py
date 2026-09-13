from django.db import models


class DntFotosCredenciales(models.Model):
    """
    Modelo para fotos de credenciales de empleados y familiares.
    Migrado de Flask/MySQL → Django/PostgreSQL.
    FOTO se almacena como bytes (BinaryField) comprimido con zlib.
    """

    id_empleado     = models.IntegerField(db_column='ID_EMPLEADO')
    tipo_foto       = models.CharField(max_length=40, null=True, blank=True, db_column='TIPO_FOTO')
    foto            = models.BinaryField(null=True, blank=True, db_column='FOTO')
    fecha_toma      = models.DateTimeField(auto_now_add=True, db_column='FECHA_TOMA')
    fec_actualizacion = models.DateTimeField(auto_now=True, null=True, blank=True, db_column='FEC_ACTUALIZACION')
    pk_num          = models.IntegerField(null=True, blank=True, db_column='PK_NUM')
    id_clave_foto   = models.IntegerField(null=True, blank=True, db_column='ID_CLAVE_FOTO')

    class Meta:
        app_label = 'administracion'
        db_table   = 'dnt_fotos_credenciales'
        managed    = False  # Tabla creada por backend/storage/expedientes-ddl, no por Django.
        # Llave primaria compuesta simulada con unique_together
        unique_together = [('id_empleado', 'id_clave_foto')]
        # Django no soporta PKs compuestas nativamente; usamos el id auto por defecto
        # y mantenemos unique_together para integridad.

    def __str__(self):
        return f"Foto {self.tipo_foto} – Empleado {self.id_empleado}"