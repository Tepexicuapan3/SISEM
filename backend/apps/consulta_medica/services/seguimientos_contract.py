"""
Contrato de lectura para otros dominios: seguimientos que indicó el médico
al cerrar la nota (``VisitConsultation.follow_up_date``, antes
``his_notas.fe_cita``). Es una indicación, no una cita: recepción lo usa para
saber a quién le falta agendar la cita (``seguimientos_por_agendar_usecase``)
sin leer las tablas de consulta médica.
"""

from apps.consulta_medica.models import VisitConsultation
from apps.consulta_medica.services.paciente_entrada import llave_publica


def _nombre_usuario(usuario) -> str:
    detalle = getattr(usuario, "detalle", None)
    if detalle is not None and detalle.nombre_completo:
        return detalle.nombre_completo
    return usuario.usuario


def seguimientos_indicados(*, fecha_desde, fecha_hasta, alcance=None) -> list[dict]:
    """
    Notas cerradas (no borradas) con fecha de seguimiento en el rango,
    ordenadas por fecha. ``alcance``: centros de quien consulta (por el centro
    de la visita).
    """
    qs = (
        VisitConsultation.objects
        .filter(
            follow_up_date__gte=fecha_desde,
            follow_up_date__lte=fecha_hasta,
            deleted_at__isnull=True,
            id_visit__status="cerrada",
        )
        .select_related("id_visit__patient", "doctor__detalle")
        .order_by("follow_up_date", "id_consultation")
    )
    if alcance is not None:
        qs = qs.filter(alcance.q("id_visit__centro_id"))
    seguimientos = []
    for consulta in qs:
        visit = consulta.id_visit
        no_exp, pk_num = llave_publica(visit)
        seguimientos.append({
            "visitId":          visit.id_visit,
            "visitFolio":       visit.folio,
            "idPaciente":       visit.patient_id,
            "noExp":            no_exp,
            "pkNum":            pk_num,
            "fechaSeguimiento": consulta.follow_up_date,
            "fechaConsulta":    visit.fecha_consulta,
            "medicoUsuarioId":  consulta.doctor_id,
            "medicoNombre":     _nombre_usuario(consulta.doctor),
            "centroId":         visit.centro_id,
            "serviceType":      visit.service_type,
        })
    return seguimientos
