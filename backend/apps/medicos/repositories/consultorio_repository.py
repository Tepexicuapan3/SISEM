from datetime import date

from apps.catalogos.models import Consultorios
from apps.medicos.models import RelMedicoConsultorio, RelMedicoConsultorioHorario


class ConsultorioRepository:
    @staticmethod
    def list_active_for_medico(medico):
        return RelMedicoConsultorio.objects.select_related(
            "consultorio"
        ).prefetch_related("horarios").filter(medico=medico, is_active=True)

    @staticmethod
    def get_catalogo(consultorio_id):
        return Consultorios.objects.filter(id=consultorio_id).first()

    @staticmethod
    def get_asignacion(*, rmc_id, medico_id):
        return RelMedicoConsultorio.objects.select_related("consultorio").filter(
            id=rmc_id, medico_id=medico_id
        ).first()

    @staticmethod
    def get_with_horarios(rmc_id):
        return RelMedicoConsultorio.objects.prefetch_related("horarios").get(id=rmc_id)

    @staticmethod
    def create(*, medico, consultorio, tipo_asignacion, fecha_inicio, fecha_fin, created_by_id):
        return RelMedicoConsultorio.objects.create(
            medico=medico,
            consultorio=consultorio,
            tipo_asignacion=tipo_asignacion,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            created_by_id=created_by_id,
        )

    @staticmethod
    def update(rmc, *, consultorio=None, tipo_asignacion=None):
        if consultorio is not None:
            rmc.consultorio = consultorio
        if tipo_asignacion is not None:
            rmc.tipo_asignacion = tipo_asignacion
        rmc.save()
        return rmc

    @staticmethod
    def deactivate(*, medico_id, rmc_id):
        RelMedicoConsultorio.objects.filter(id=rmc_id, medico_id=medico_id).update(
            is_active=False, fecha_fin=date.today()
        )

    @staticmethod
    def create_horarios(rmc, horarios_payload):
        for h in horarios_payload:
            RelMedicoConsultorioHorario.objects.create(
                rel_medico_consultorio=rmc,
                dia_semana=h["diaSemana"],
                hora_inicio=h["horaInicio"],
                hora_fin=h["horaFin"],
                intervalo_cita_min=h.get("intervaloCitaMin", 20),
                canal=h.get("canal", "PRESENCIAL"),
            )

    @staticmethod
    def replace_horarios(rmc, horarios_payload):
        rmc.horarios.all().delete()
        ConsultorioRepository.create_horarios(rmc, horarios_payload)
