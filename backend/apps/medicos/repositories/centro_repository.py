from datetime import date

from apps.catalogos.models import CatCentroAtencion
from apps.medicos.models import RelMedicoCentro


class CentroRepository:
    @staticmethod
    def get_catalogo(centro_id):
        return CatCentroAtencion.objects.filter(id=centro_id).first()

    @staticmethod
    def create(*, medico, centro, tipo_adscripcion, fecha_inicio, fecha_fin, created_by_id):
        return RelMedicoCentro.objects.create(
            medico=medico,
            centro=centro,
            tipo_adscripcion=tipo_adscripcion,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            created_by_id=created_by_id,
        )

    @staticmethod
    def deactivate(*, medico_id, rel_id):
        RelMedicoCentro.objects.filter(id=rel_id, medico_id=medico_id).update(
            is_active=False, fecha_fin=date.today()
        )
