from apps.medicos.models import RelMedicoExcepcion


class ExcepcionRepository:
    @staticmethod
    def list_active(medico_id):
        return RelMedicoExcepcion.objects.filter(
            medico_id=medico_id, is_active=True
        ).order_by("fecha_inicio")

    @staticmethod
    def create(*, medico, tipo, fecha_inicio, fecha_fin, hora_inicio, hora_fin,
               consultorio_id, motivo, created_by_id):
        return RelMedicoExcepcion.objects.create(
            medico=medico,
            tipo=tipo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            consultorio_id=consultorio_id,
            motivo=motivo,
            created_by_id=created_by_id,
        )

    @staticmethod
    def deactivate(*, medico_id, exc_id):
        RelMedicoExcepcion.objects.filter(id=exc_id, medico_id=medico_id).update(is_active=False)
