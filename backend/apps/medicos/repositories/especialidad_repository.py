from apps.catalogos.models import Especialidades
from apps.medicos.models import RelMedicoEspecialidad


class EspecialidadRepository:
    @staticmethod
    def get_catalogo(especialidad_id):
        return Especialidades.objects.filter(id=especialidad_id).first()

    @staticmethod
    def unset_principal(medico):
        RelMedicoEspecialidad.objects.filter(medico=medico, es_principal=True).update(es_principal=False)

    @staticmethod
    def upsert(*, medico, especialidad, es_principal):
        rel, created = RelMedicoEspecialidad.objects.get_or_create(
            medico=medico, especialidad=especialidad,
            defaults={"es_principal": es_principal},
        )
        if not created:
            rel.es_principal = es_principal
            rel.save()
        return rel, created

    @staticmethod
    def delete(*, medico_id, especialidad_id):
        RelMedicoEspecialidad.objects.filter(
            medico_id=medico_id, especialidad_id=especialidad_id
        ).delete()
