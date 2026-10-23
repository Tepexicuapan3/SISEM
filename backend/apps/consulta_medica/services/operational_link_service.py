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
}
# Tablas que solo se vinculan a un registro existente (no lo crean).
ONLY_LINK = frozenset({"portal_citas.PortalMiembro"})


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


def _link_on_save(sender, instance, **kwargs):
    if instance.patient_id is not None:
        return
    patient = resolve_record(
        sender, getattr(instance, no_exp_field(sender)), instance.pk_num,
        created_by_id=getattr(instance, "created_by_id", None),
    )
    if patient is not None:
        instance.patient = patient


def connect_operational_signals():
    for model in operational_models():
        pre_save.connect(_link_on_save, sender=model, dispatch_uid=f"link_operational_{model._meta.label}")
