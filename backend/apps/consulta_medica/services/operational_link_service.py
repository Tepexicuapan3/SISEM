"""
Plan identidad del paciente, Fase 5: las tablas operativas (visitas, citas,
signos vitales, cirugias, hospitalizacion, ambulancias, pases, contratos de
oxigeno, portal) guardan id_paciente: el REGISTRO (afiliacion) atendido, no
la persona. Mismo patron que las tablas clinicas (etapas 7a-7e,
patient_link_service):

  - doble escritura: al guardar una fila sin id_paciente se resuelve aqui
    (senal pre_save) y se siguen guardando no_exp/pk_num como antes;
  - lo existente se llena con vincular_id_paciente (link_existing);
  - las lecturas por id_paciente se encienden con
    IDENTIDAD_LECTURA_OPERATIVA_POR_ID (se suman a las de por llave: no se
    pierde nada al encenderlo).

El registro nace en cuanto se inicia cualquier cosa del paciente (decision
del 2026-10-22): una cita, una visita o una solicitud crean el registro por la
puerta central (PatientRepository.get_or_create, que normaliza y verifica en
SERMED segun el interruptor de la Fase 1). La cuenta del portal no es
atencion: solo se vincula si el registro ya existe.

OJO: queryset.update() y bulk_create() no disparan senales; despues de una
importacion masiva hay que volver a correr vincular_id_paciente.
"""
from __future__ import annotations

from django.apps import apps
from django.db.models.signals import pre_save

# tabla -> nombre del campo con el expediente (casi siempre no_exp).
OPERATIONAL_MODELS = {
    "recepcion.Visit": "no_exp",
    "recepcion.CitaMedica": "no_exp",
    "somatometria.VisitVitalSigns": "no_exp",
    "somatometria.PatientLatestVitals": "no_exp",
    "cirugias.SurgerySchedule": "no_exp",
    "hospitalizacion.HospitalAdmission": "no_exp",
    "ambulancias.AmbulanceRequest": "no_exp",
    "pases.Referral": "no_exp",
    "contratos_oxigeno.ContratoOxigeno": "expediente",
    "portal_citas.PortalMiembro": "no_exp",
    "padrones.ChronicEnrollment": "no_exp",
    "padrones.DisabilityEnrollment": "no_exp",
}
# Tablas que solo se vinculan a un registro existente (no lo crean).
ONLY_LINK = frozenset({"portal_citas.PortalMiembro"})

# Plan contraer la llave vieja (C6): estas tablas guardan SOLO id_paciente.
# Si alguien todavia manda la llave al crear, sirve para resolver el registro
# y despues se vacia: nunca llega a la base. La llave se lee de cns_paciente
# (paciente_entrada.llave_publica).
SIN_LLAVE = frozenset({
    "recepcion.Visit", "recepcion.CitaMedica",
    "somatometria.VisitVitalSigns", "somatometria.PatientLatestVitals",
    "consulta_medica.Allergy", "consulta_medica.MedicalLeave", "consulta_medica.StudyResult",
    "consulta_medica.StomatologyHistory", "consulta_medica.Odontogram", "consulta_medica.ClinicalHistory",
    "consulta_medica.PersonalHistory", "consulta_medica.FamilyHistory", "consulta_medica.SurgicalHistory",
    "consulta_medica.Habit", "consulta_medica.DentalTreatment",
    "cirugias.SurgerySchedule", "hospitalizacion.HospitalAdmission", "ambulancias.AmbulanceRequest",
    "pases.Referral", "contratos_oxigeno.ContratoOxigeno",
    "padrones.ChronicEnrollment", "padrones.DisabilityEnrollment",
})


def paciente_de_la_visita(instance):
    """
    id_paciente de la visita de la que cuelga una fila (pase, estudio, licencia,
    signos...), para quien llega sin paciente y sin llave: la visita congelada
    ya no guarda no_exp/pk_num, pero si su id_paciente.
    """
    visita_id = getattr(instance, "id_visit_id", None)
    if visita_id is None and getattr(instance, "consultation_id", None):
        visita_id = getattr(instance.consultation, "id_visit_id", None)
    if visita_id is None:
        return None
    from apps.recepcion.models import Visit

    return Visit.objects.filter(pk=visita_id).values_list("patient_id", flat=True).first()


def congelar_llave(sender, instance) -> None:
    """Vacia la llave vieja de una fila ya ligada a su paciente (tablas SIN_LLAVE)."""
    if sender._meta.label in SIN_LLAVE and instance.patient_id is not None:
        setattr(instance, no_exp_field(sender), None)
        instance.pk_num = None


def operational_models():
    return [apps.get_model(label) for label in OPERATIONAL_MODELS]


def creates_record(model) -> bool:
    return model._meta.label not in ONLY_LINK


def no_exp_field(model) -> str:
    """Campo con el expediente: "no_exp" salvo excepciones (contratos: "expediente")."""
    return OPERATIONAL_MODELS.get(model._meta.label, "no_exp")


def resolve_record(model, no_exp, pk_num, *, created_by_id=None):
    """Registro de cns_paciente para (no_exp, pk_num), creandolo por la puerta
    central si la tabla lo permite. None si no hay llave o no corresponde."""
    from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
    from apps.consulta_medica.services.patient_link_service import find_patient_by_record_key

    if not no_exp or pk_num is None:
        return None
    patient = find_patient_by_record_key(no_exp, pk_num)
    if patient is None and creates_record(model):
        patient, _ = PatientRepository.get_or_create(no_exp, pk_num, created_by_id=created_by_id)
    return patient


# Donde empieza la atencion: con un recien nacido pendiente de vincular no se
# abre ficha ni cita (ni para el provisional ni para el familiar de SERMED).
ATTENTION_ENTRY = frozenset({"recepcion.Visit", "recepcion.CitaMedica"})


def _link_on_save(sender, instance, **kwargs):
    if instance._state.adding and sender._meta.label in ATTENTION_ENTRY:
        from apps.consulta_medica.services.newborn_service import exigir_vinculacion_para_atender

        exigir_vinculacion_para_atender(getattr(instance, no_exp_field(sender)), instance.pk_num)
    if instance.patient_id is not None:
        congelar_llave(sender, instance)
        return
    patient = resolve_record(
        sender, getattr(instance, no_exp_field(sender)), instance.pk_num,
        created_by_id=getattr(instance, "created_by_id", None),
    )
    if patient is not None:
        instance.patient = patient
    elif sender._meta.label in SIN_LLAVE:
        instance.patient_id = paciente_de_la_visita(instance)
    congelar_llave(sender, instance)


def connect_operational_signals():
    for model in operational_models():
        pre_save.connect(_link_on_save, sender=model, dispatch_uid=f"link_operational_{model._meta.label}")
