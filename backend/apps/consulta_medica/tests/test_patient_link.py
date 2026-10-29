"""
5.1 paso 7: las tablas clinicas apuntan al paciente por id_paciente. Quedan la
resolucion de una llave y la lectura por paciente; la escritura doble y el
vinculo masivo se retiraron en C7 (plan contraer la llave vieja).
"""
from datetime import date
from django.test import TestCase

from apps.consulta_medica.models import (
    Allergy,
    LegacyConsultationRecord,
    Patient,
)
from apps.consulta_medica.repositories.allergy_repository import AllergyRepository
from apps.consulta_medica.repositories.legacy_consultation_repository import LegacyConsultationRepository
from apps.consulta_medica.services.patient_link_service import (
    find_patient_by_record_key,
    for_patient,
)
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


def _allergy(no_exp, pk_num, substance="Penicilina"):
    return Allergy.objects.create(
        patient=_paciente_de_llave(no_exp, pk_num), allergy_type_id=1, substance=substance,
        service_origin_code=Allergy.SERVICE_BY_SOURCE[Allergy.Source.GENERAL],
    )


def _legacy_note(folio, no_exp, pk_num):
    return LegacyConsultationRecord(
        legacy_folio=folio, no_exp=no_exp, pk_num=pk_num, consultation_date=date(2020, 1, 1),
    )


class FindPatientByRecordKeyTests(TestCase):
    def test_busca_por_llave_y_por_cd_familiar_del_legado(self):
        titular = Patient.objects.create(no_exp="10", pk_num=0)
        sin_pk = Patient.objects.create(no_exp="10", pk_num=None, legacy_family_code=55)

        self.assertEqual(find_patient_by_record_key("10", 0), titular)
        self.assertEqual(find_patient_by_record_key("10", 55), sin_pk)
        self.assertIsNone(find_patient_by_record_key("10", 77))
        # El cd_familiar es de ese titular: con otro no_exp no aparece.
        self.assertIsNone(find_patient_by_record_key("11", 55))


class ReadsByPatientTests(TestCase):
    """7d: las pantallas leen por id_paciente (con las filas aun sin vincular)."""

    def test_aparecen_los_registros_del_paciente_aunque_tengan_otra_llave(self):
        # Paciente fusionado o familiar con otra llave: lo que manda es id_paciente.
        paciente = Patient.objects.create(no_exp="50", pk_num=0)
        otra_llave = _allergy("99", 0, "Latex")
        Allergy.objects.filter(pk=otra_llave.pk).update(patient=paciente)

        sustancias = {a.substance for a in AllergyRepository.list_for_patient("50", 0)}

        self.assertIn("Latex", sustancias)

    def test_hasta_el_not_null_tambien_aparecen_las_filas_sin_vincular(self):
        Patient.objects.create(no_exp="51", pk_num=0)
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("H1", "51", 0)])

        self.assertEqual(LegacyConsultationRepository.count_for_patient("51", 0), 1)

    def test_sin_paciente_se_leen_las_filas_de_la_llave(self):
        _allergy("52", 0, "Polen")

        self.assertEqual([a.substance for a in AllergyRepository.list_for_patient("52", 0)], ["Polen"])

    def test_no_aparece_lo_vinculado_a_otro_paciente_aunque_comparta_llave(self):
        Patient.objects.create(no_exp="53", pk_num=0)
        otro = Patient.objects.create(no_exp="54", pk_num=0)
        ajena = _allergy("53", 0, "Sulfas")
        Allergy.objects.filter(pk=ajena.pk).update(patient=otro)

        self.assertEqual(list(AllergyRepository.list_for_patient("53", 0)), [])

    def test_familiar_sin_pk_num_ve_su_historia_con_el_cd_familiar(self):
        paciente = Patient.objects.create(no_exp="55", pk_num=None, legacy_family_code=44)
        _allergy("55", 44, "Ibuprofeno")

        alergias = list(AllergyRepository.list_for_patient("55", 44))

        self.assertEqual([a.substance for a in alergias], ["Ibuprofeno"])
        self.assertEqual(alergias[0].patient, paciente)

    def test_for_patient_no_mezcla_titular_y_familiar(self):
        Patient.objects.create(no_exp="56", pk_num=0)
        Patient.objects.create(no_exp="56", pk_num=7)
        _allergy("56", 0, "Titular")
        _allergy("56", 7, "Familiar")

        self.assertEqual(
            [a.substance for a in for_patient(Allergy.objects.all(), "56", 7)], ["Familiar"],
        )


