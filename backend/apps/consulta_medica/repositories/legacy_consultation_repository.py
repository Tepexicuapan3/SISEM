from apps.consulta_medica.models import LegacyConsultationRecord

# Un paciente puede acumular cientos de notas en 1.7 anios de legado --
# se limita a las mas recientes en vez de paginar completo (alcance
# chico a proposito, ver memoria sdd/historia-clinica-migracion/his-notas).
_MAX_RESULTS = 200


class LegacyConsultationRepository:
    @staticmethod
    def list_for_patient(no_exp, pk_num):
        return LegacyConsultationRecord.objects.filter(
            no_exp=no_exp, pk_num=pk_num,
        )[:_MAX_RESULTS]

    @staticmethod
    def count_for_patient(no_exp, pk_num):
        return LegacyConsultationRecord.objects.filter(
            no_exp=no_exp, pk_num=pk_num,
        ).count()

    @staticmethod
    def to_contract(record):
        return {
            "id": record.id_legacy_record,
            "legacyFolio": record.legacy_folio,
            "date": record.consultation_date,
            "time": record.consultation_time,
            "doctorCodeLegacy": record.doctor_code_legacy,
            "clinicCodeLegacy": record.clinic_code_legacy,
            "subjective": record.subjective,
            "objective": record.objective,
            "assessment": record.assessment,
            "plan": record.plan,
            "diagnosticImpression": record.diagnostic_impression,
            "primaryCieCodeLegacy": record.primary_cie_code_legacy,
            "addendumLegacy": record.addendum_legacy,
            "weightLegacy": record.weight_legacy,
            "heightLegacy": record.height_legacy,
            "bloodPressureLegacy": record.blood_pressure_legacy,
            "pulseLegacy": record.pulse_legacy,
            "temperatureLegacy": record.temperature_legacy,
            "isFirstVisitLegacy": record.is_first_visit_legacy,
        }
