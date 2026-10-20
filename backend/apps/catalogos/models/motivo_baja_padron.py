# Catalogo de motivos de baja de una inscripcion a padron clinico (cronicos o
# discapacidad), change padrones-clinicos (P-04). Mismo patron que
# motivo_cancelacion_nota.py. A diferencia del legado (cat_motivobajacron, solo
# motivos laborales y baja del paciente completo), la baja es por inscripcion
# e incluye motivos clinicos.
from django.db import models
from .base import CatalogBase


class MotivoBajaPadron(CatalogBase):
    id = models.BigAutoField(primary_key=True, db_column="id_motivo_baja_padron")
    name = models.CharField(max_length=200, db_column="nombre")

    class Meta:
        db_table = "cat_motivo_baja_padron"
        managed = True
