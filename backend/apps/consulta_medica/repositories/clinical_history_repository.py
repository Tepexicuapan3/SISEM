import logging

from django.db import transaction
from django.utils import timezone

from apps.consulta_medica.models import ChangeLog, ClinicalHistory, Patient, PatientRevision
from apps.consulta_medica.services.change_log_service import PROCESS_SIRES
from apps.consulta_medica.services.patient_identifier_service import (
    IdentifierConflict,
    register_column_identifiers,
)
from apps.consulta_medica.services.patient_link_service import find_patient_by_record_key
from apps.consulta_medica.services.patient_registry_service import (
    ORIGEN_ATENCION,
    normalizar_no_exp,
    verificar_alta,
)
from apps.consulta_medica.services.paciente_entrada import llave_publica

logger = logging.getLogger(__name__)

# Campos editables de PACIENTE -- mismo set que PATIENT_FIELD_MAP en
# clinical_history_usecase.py. Se usa para saber que "previous_<campo>"
# snapshotear en PatientRevision.
_VERSIONED_FIELDS = (
    "curp",
    "sex",
    "occupation_id",
    "education_level_id",
    "marital_status_id",
    "religion_id",
    "residence_type_id",
    "phone",
)


class PatientRepository:
    """PACIENTE: datos de la persona (1 por no_exp + pk_num, o por cd_familiar)."""

    @staticmethod
    def get_or_create(no_exp, pk_num, *, created_by_id=None, origen=ORIGEN_ATENCION):
        """
        Unica puerta de entrada para crear un registro de paciente (plan
        identidad, Fase 1): normaliza el no_exp y, antes de crear, verifica en
        SERMED segun el origen (ver services/patient_registry_service.py).
        Segura ante concurrencia: la restriccion unica (no_exp, pk_num) mas
        get_or_create dejan un solo registro (test_concurrencia_paciente).
        """
        recibido = str(no_exp).strip()
        no_exp = normalizar_no_exp(no_exp)
        with transaction.atomic():
            # Incluye al familiar del legado sin PK_NUM (pk_num NULL, registros
            # con el cd_familiar como llave): ver find_patient_by_record_key.
            existing = find_patient_by_record_key(no_exp, pk_num)
            if existing is None and recibido != no_exp:
                # Un registro anterior guardado sin normalizar ("040041"):
                # se usa ese, nunca se crea un segundo de la misma afiliacion.
                existing = find_patient_by_record_key(recibido, pk_num)
                if existing:
                    logger.warning(
                        "Paciente %s guardado con no_exp sin normalizar %r", existing.pk, recibido,
                    )
            if existing:
                return existing, False
            verificar_alta(no_exp, pk_num, origen=origen, created_by_id=created_by_id)
            # Plan identidad, guardia 1: un familiar que coincide con un recien
            # nacido provisional pendiente se vincula antes de abrirle registro.
            from apps.consulta_medica.services.newborn_service import verificar_rn_pendiente

            verificar_rn_pendiente(no_exp, pk_num, origen=origen)
            patient, created = Patient.objects.get_or_create(no_exp=no_exp, pk_num=pk_num)
            if created:
                PatientRepository._register_identifiers(patient, created_by_id)
                # Puente al historial del legado (CD_FAMILIAR). Despues del commit:
                # nunca frena ni revierte el alta; si falla, lo completa la recarga.
                from apps.consulta_medica.services.legado_llaves import registrar_al_abrir

                transaction.on_commit(lambda: registrar_al_abrir(patient))
        return patient, created

    @staticmethod
    def _register_identifiers(patient, created_by_id):
        """Alta del NO_EXP del titular nuevo. Los familiares NO: por aqui
        tambien entra la importacion del legado, que hoy pasa cd_familiar como
        pk_num (bug documentado); sus identificadores se registran al corregir
        ese mapeo y en la sincronizacion con SERMED, donde el valor se verifica.
        Un conflicto no frena la atencion: se registra para revisarlo."""
        try:
            register_column_identifiers(
                patient, reason=ChangeLog.Reason.PATIENT_OPENED,
                user=created_by_id if created_by_id is not None else PROCESS_SIRES,
                include_family=False,
            )
        except IdentifierConflict as exc:
            logger.warning("Identificador en conflicto al abrir paciente %s: %s", patient.pk, exc)

    @staticmethod
    def update(patient, *, fields, updated_by_id=None):
        # Captura incremental: rellenar un campo vacio por primera vez no es
        # alterar un dato -- solo versiona cuando YA habia un valor concreto
        # y se sobreescribe con otro (NOM-024: nada se pisa sin rastro).
        changed = any(
            getattr(patient, field_name) not in (None, "") and getattr(patient, field_name) != value
            for field_name, value in fields.items()
        )
        if changed:
            PatientRevision.objects.create(
                patient=patient,
                changed_by_id=updated_by_id,
                **{f"previous_{field_name}": getattr(patient, field_name) for field_name in _VERSIONED_FIELDS},
            )
        for field_name, value in fields.items():
            setattr(patient, field_name, value)
        patient.updated_by_id = updated_by_id
        patient.save()
        return patient

    @staticmethod
    def to_contract(patient):
        return {
            "id": patient.id_patient,
            "uuid": str(patient.uuid),
            "noExp": patient.no_exp,
            "pkNum": patient.pk_num,
            "legacyFamilyCode": patient.legacy_family_code,
            "provisionalCode": patient.provisional_code,
            # Copiados de SERMED: solo lectura en SIRES.
            "paternalSurname": patient.paternal_surname,
            "maternalSurname": patient.maternal_surname,
            "firstName": patient.first_name,
            "birthDate": patient.birth_date.isoformat() if patient.birth_date else None,
            "curp": patient.curp,
            # "O" = viene de SERMED (no editable), "C" = capturada en SIRES.
            "curpSource": patient.curp_source,
            "sex": patient.sex,
            "occupationId": patient.occupation_id,
            "educationLevelId": patient.education_level_id,
            "maritalStatusId": patient.marital_status_id,
            "religionId": patient.religion_id,
            "residenceTypeId": patient.residence_type_id,
            "phone": patient.phone,
            "createdAt": patient.created_at,
            "updatedAt": patient.updated_at,
        }


class ClinicalHistoryRepository:
    """HISTORIA_CLINICA: cabecera unica por paciente, 1:1 con PACIENTE."""

    @staticmethod
    def get_or_create_for_patient(no_exp, pk_num, *, opened_on=None, clinic_code=None,
                                  doctor_code=None, created_by_id=None, origen=ORIGEN_ATENCION):
        with transaction.atomic():
            patient, _ = PatientRepository.get_or_create(
                no_exp, pk_num, created_by_id=created_by_id, origen=origen,
            )
            # Plan contraer la llave vieja: una cabecera por registro del paciente.
            history, created = ClinicalHistory.objects.get_or_create(
                patient=patient,
                defaults={
                    "opened_on": opened_on or timezone.localdate(),
                    "opening_clinic_code": clinic_code,
                    "opening_doctor_code": doctor_code,
                    "created_by_id": created_by_id,
                },
            )
        return history, created

    @staticmethod
    def to_contract(history):
        return {
            "id": history.id_clinical_history,
            "noExp": llave_publica(history)[0],
            "pkNum": llave_publica(history)[1],
            "patientId": history.patient_id,
            "openedOn": history.opened_on.isoformat() if history.opened_on else None,
            "openingClinicCode": history.opening_clinic_code,
            "openingDoctorCode": history.opening_doctor_code,
            # De que fila del legado salio (his_clinica / his_clinicad); null = abierta en SIRES.
            "legacySourceTable": history.legacy_source_table,
            "legacySourceId": history.legacy_source_id,
            "isActive": history.is_active,
            "createdAt": history.created_at,
        }
