"""
Plan identidad del paciente, Fase 5: las tablas operativas (visitas, citas,
signos vitales, cirugias, hospitalizacion, ambulancias, pases, contratos de
oxigeno, portal) guardan id_paciente: el REGISTRO (afiliacion) atendido, no
la persona. Mismo patron que las tablas clinicas (etapas 7a-7e,
patient_link_service):

  - C7 (plan contraer la llave vieja): esas tablas ya no tienen no_exp/pk_num;
    guardan solo id_paciente (SIN_LLAVE). Solo la cuenta del portal conserva
    la llave y se vincula por ella al registro que exista.

El registro nace en cuanto se inicia cualquier cosa del paciente (decision
del 2026-10-22): una cita, una visita o una solicitud crean el registro por la
puerta central (PatientRepository.get_or_create, que normaliza y verifica en
SERMED segun el interruptor de la Fase 1). La cuenta del portal no es
atencion: solo se vincula si el registro ya existe.
"""
from __future__ import annotations

from django.apps import apps
from django.db.models.signals import pre_save

# Tablas que todavia guardan la llave y se vinculan a un registro existente
# por ella (no lo crean): la cuenta del portal no es atencion.
OPERATIONAL_MODELS = {
    "portal_citas.PortalMiembro": "no_exp",
}
ONLY_LINK = frozenset({"portal_citas.PortalMiembro"})

# Plan contraer la llave vieja: estas tablas guardan SOLO id_paciente (C6
# vacio la llave, C7 borro las columnas). La llave se lee de cns_paciente
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
    signos...), para quien llega sin paciente: la visita guarda su id_paciente.
    """
    visita_id = getattr(instance, "id_visit_id", None)
    if visita_id is None and getattr(instance, "consultation_id", None):
        visita_id = getattr(instance.consultation, "id_visit_id", None)
    if visita_id is None:
        return None
    from apps.recepcion.models import Visit

    return Visit.objects.filter(pk=visita_id).values_list("patient_id", flat=True).first()


def operational_models():
    return [apps.get_model(label) for label in OPERATIONAL_MODELS]


def creates_record(model) -> bool:
    return model._meta.label not in ONLY_LINK


def no_exp_field(model) -> str:
    """Campo con el expediente de las tablas que todavia guardan la llave."""
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
    """Tablas con llave (portal): se vinculan al registro que ya exista."""
    if instance.patient_id is None:
        patient = resolve_record(sender, getattr(instance, no_exp_field(sender)), instance.pk_num)
        if patient is not None:
            instance.patient = patient


def _completar_paciente(sender, instance, **kwargs):
    """
    Tablas SIN_LLAVE: quien no trae paciente lo toma de la visita de la que
    cuelga. Al abrir una ficha o una cita se aplica la regla del recien nacido
    pendiente de vincular, con la llave del registro (cns_paciente).
    """
    if instance.patient_id is None:
        instance.patient_id = paciente_de_la_visita(instance)
    if instance._state.adding and sender._meta.label in ATTENTION_ENTRY and instance.patient_id:
        from apps.consulta_medica.services.newborn_service import exigir_vinculacion_para_atender
        from apps.consulta_medica.services.paciente_entrada import llave_de_paciente

        llave = llave_de_paciente(instance.patient_id)
        if llave is not None:
            exigir_vinculacion_para_atender(*llave)


def connect_operational_signals():
    for model in operational_models():
        pre_save.connect(_link_on_save, sender=model, dispatch_uid=f"link_operational_{model._meta.label}")
    for label in SIN_LLAVE:
        pre_save.connect(_completar_paciente, sender=apps.get_model(label),
                         dispatch_uid=f"completar_paciente_{label}")
