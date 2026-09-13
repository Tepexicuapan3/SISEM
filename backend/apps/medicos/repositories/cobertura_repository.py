from datetime import date

from django.db.models import Q

from apps.medicos.models import RelMedicoCobertura, RelMedicoCoberturaHorario


class CoberturaRepository:
    @staticmethod
    def list_for_medico(medico):
        return RelMedicoCobertura.objects.select_related(
            "medico_suplente__id_usuario__detalle",
            "medico_titular__id_usuario__detalle",
            "consultorio", "centro",
        ).prefetch_related("horarios").filter(
            Q(medico_suplente=medico) | Q(medico_titular=medico),
            is_active=True,
        ).order_by("-fecha_inicio")

    @staticmethod
    def get_by_id(cobertura_id):
        return RelMedicoCobertura.objects.filter(id=cobertura_id).first()

    @staticmethod
    def get_with_horarios(cobertura_id):
        return RelMedicoCobertura.objects.prefetch_related("horarios").get(id=cobertura_id)

    @staticmethod
    def create(*, suplente, titular, consultorio_id, centro_id, fecha_inicio, fecha_fin,
               motivo, created_by_id):
        return RelMedicoCobertura.objects.create(
            medico_suplente=suplente,
            medico_titular=titular,
            consultorio_id=consultorio_id,
            centro_id=centro_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            motivo=motivo,
            created_by_id=created_by_id,
        )

    @staticmethod
    def create_horarios(cobertura, horarios_payload):
        for h in horarios_payload:
            RelMedicoCoberturaHorario.objects.create(
                cobertura=cobertura,
                dia_semana=h["diaSemana"],
                hora_inicio=h["horaInicio"],
                hora_fin=h["horaFin"],
            )

    @staticmethod
    def cancel(cobertura):
        cobertura.is_active = False
        if not cobertura.fecha_fin or cobertura.fecha_fin > date.today():
            cobertura.fecha_fin = date.today()
        cobertura.save(update_fields=["is_active", "fecha_fin"])
        return cobertura
