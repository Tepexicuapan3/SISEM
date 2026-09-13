from django.db import models


class CatFamiliar(models.Model):
    """
    Catálogo de familiares de empleados.
    Tabla replicada desde Oracle.
    """

    pk_num          = models.IntegerField(primary_key=True, db_column='pk_num')
    no_expf         = models.CharField(max_length=20, db_column='no_expf')
    ds_paterno      = models.CharField(max_length=100, null=True, blank=True, db_column='ds_paterno')
    ds_materno      = models.CharField(max_length=100, null=True, blank=True, db_column='ds_materno')
    ds_nombre       = models.CharField(max_length=100, null=True, blank=True, db_column='ds_nombre')
    cd_parentesco   = models.CharField(max_length=50,  null=True, blank=True, db_column='cd_parentesco')
    tp_der          = models.CharField(max_length=2,  null=True, blank=True, db_column='tp_der')
    fe_nac          = models.DateField(null=True, blank=True, db_column='fe_nac')
    no_edad         = models.IntegerField(null=True, blank=True, db_column='no_edad')
    fec_vig         = models.DateField(null=True, blank=True, db_column='fec_vig')
    cd_clinica      = models.CharField(max_length=10,  null=True, blank=True, db_column='cd_clinica')
    curp            = models.CharField(max_length=18,  null=True, blank=True, db_column='curp')
    fec_ult_actualizacion = models.DateTimeField(null=True, blank=True, db_column='fec_ult_actualizacion')

    class Meta:
        app_label = 'administracion'
        db_table  = 'cat_familiar'
        managed   = False

    def __str__(self):
        return f"PKN {self.pk_num} – {self.ds_nombre} (Exp: {self.no_expf})"