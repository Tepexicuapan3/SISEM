from django.db import models


class CatEmpleado(models.Model):
    """
    Catálogo de empleados.
    Tabla replicada desde Oracle; los datos llegan vía el servicio de sincronización.
    """

    no_exp              = models.CharField(max_length=20, primary_key=True, db_column='no_exp')
    ds_paterno          = models.CharField(max_length=100, null=True, blank=True, db_column='ds_paterno')
    ds_materno          = models.CharField(max_length=100, null=True, blank=True, db_column='ds_materno')
    ds_nombre           = models.CharField(max_length=100, null=True, blank=True, db_column='ds_nombre')
    cd_laboral          = models.CharField(max_length=100, null=True, blank=True, db_column='cd_laboral')
    cve_cd_laboral      = models.CharField(max_length=10,  null=True, blank=True, db_column='cve_cd_laboral')
    cve_baja            = models.CharField(max_length=10,  null=True, blank=True, db_column='cve_baja')
    fec_baja            = models.DateField(null=True, blank=True, db_column='fec_baja')
    fe_nac              = models.DateField(null=True, blank=True, db_column='fe_nac')
    fec_vig             = models.DateField(null=True, blank=True, db_column='fec_vig')
    no_edad             = models.IntegerField(null=True, blank=True, db_column='no_edad')
    cd_clinica          = models.CharField(max_length=10,  null=True, blank=True, db_column='cd_clinica')
    curp                = models.CharField(max_length=18,  null=True, blank=True, db_column='curp')
    fec_ult_actualizacion = models.DateTimeField(null=True, blank=True, db_column='fec_ult_actualizacion')

    class Meta:
        app_label = 'administracion'
        db_table  = 'cat_empleados'
        managed   = False   # Django NO gestiona esta tabla (es replicada)

    def __str__(self):
        return f"{self.no_exp} – {self.ds_nombre} {self.ds_paterno}"