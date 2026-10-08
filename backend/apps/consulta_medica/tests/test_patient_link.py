"""
5.1 paso 7 (a, b y c): las tablas clinicas apuntan al paciente por id_paciente.
"""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.consulta_medica.models import (
    Allergy,
    ClinicalHistory,
    LegacyConsultationRecord,
    Patient,
    PersonalHistory,
)
from apps.consulta_medica.repositories.allergy_repository import AllergyRepository
from apps.consulta_medica.repositories.legacy_consultation_repository import LegacyConsultationRepository
from apps.consulta_medica.services.patient_link_service import (
    find_patient_by_record_key,
    for_patient,
    link_existing,
    linked_models,
    unlinked_counts,
)


def _allergy(no_exp, pk_num, substance="Penicilina"):
    return Allergy.objects.create(
        no_exp=no_exp, pk_num=pk_num, allergy_type_id=1, substance=substance,
        service_origin_code=Allergy.SERVICE_BY_SOURCE[Allergy.Source.GENERAL],
    )


def _legacy_note(folio, no_exp, pk_num):
    return LegacyConsultationRecord(
        legacy_folio=folio, no_exp=no_exp, pk_num=pk_num, consultation_date=date(2020, 1, 1),
    )


class LinkedModelsTests(TestCase):
    def test_incluye_las_tablas_clinicas_con_llave_de_paciente(self):
        tablas = {model._meta.db_table for model in linked_models()}

        for tabla in ("cns_allergy", "cns_legacy_consultation_record", "cns_antecedente_personal",
                      "cns_antecedente_familiar", "cns_habito", "cns_nota_historica",
                      "cns_odontograma", "cns_medical_leave", "cns_study_result"):
            self.assertIn(tabla, tablas)
        self.assertNotIn("cns_paciente", tablas)


class FindPatientByRecordKeyTests(TestCase):
    def test_busca_por_llave_y_por_cd_familiar_del_legado(self):
        titular = Patient.objects.create(no_exp="10", pk_num=0)
        sin_pk = Patient.objects.create(no_exp="10", pk_num=None, legacy_family_code=55)

        self.assertEqual(find_patient_by_record_key("10", 0), titular)
        self.assertEqual(find_patient_by_record_key("10", 55), sin_pk)
        self.assertIsNone(find_patient_by_record_key("10", 77))
        # El cd_familiar es de ese titular: con otro no_exp no aparece.
        self.assertIsNone(find_patient_by_record_key("11", 55))


class DualWriteTests(TestCase):
    def test_un_registro_nuevo_se_guarda_con_su_paciente(self):
        paciente = Patient.objects.create(no_exp="20", pk_num=0)

        alergia = _allergy("20", 0)
        antecedente = PersonalHistory.objects.create(no_exp="20", pk_num=0, description="Asma")

        self.assertEqual(alergia.patient, paciente)
        self.assertEqual(antecedente.patient, paciente)

    def test_familiar_sin_pk_num_tambien_se_vincula(self):
        paciente = Patient.objects.create(no_exp="20", pk_num=None, legacy_family_code=33)

        self.assertEqual(_allergy("20", 33).patient, paciente)

    def test_sin_paciente_el_registro_se_guarda_igual(self):
        alergia = _allergy("21", 0)

        self.assertIsNone(alergia.patient)

    def test_no_cambia_un_paciente_ya_asignado(self):
        a = Patient.objects.create(no_exp="22", pk_num=0)
        b = Patient.objects.create(no_exp="23", pk_num=0)

        alergia = Allergy(no_exp="22", pk_num=0, allergy_type_id=1, substance="X",
                          service_origin_code=Allergy.SERVICE_BY_SOURCE[Allergy.Source.GENERAL], patient=b)
        alergia.save()

        self.assertEqual(alergia.patient, b)
        self.assertNotEqual(alergia.patient, a)


class LinkExistingTests(TestCase):
    def test_vincula_lo_que_bulk_create_dejo_sin_paciente(self):
        paciente = Patient.objects.create(no_exp="30", pk_num=0)
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("A1", "30", 0), _legacy_note("A2", "30", 0)])
        self.assertEqual(unlinked_counts()["cns_legacy_consultation_record"], 2)

        reporte = link_existing()

        self.assertEqual(reporte["cns_legacy_consultation_record"]["rows"], 2)
        self.assertEqual(set(LegacyConsultationRecord.objects.values_list("patient", flat=True)), {paciente.pk})
        self.assertEqual(sum(unlinked_counts().values()), 0)

    def test_crea_el_paciente_que_falta(self):
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("B1", "31", 0)])

        reporte = link_existing()

        self.assertEqual(reporte["cns_legacy_consultation_record"]["patients_created"], 1)
        paciente = Patient.objects.get(no_exp="31", pk_num=0)
        self.assertEqual(LegacyConsultationRecord.objects.get(legacy_folio="B1").patient, paciente)

    def test_sin_crear_deja_las_filas_sin_vincular(self):
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("C1", "32", 0)])

        reporte = link_existing(create_missing=False)

        self.assertEqual(reporte["cns_legacy_consultation_record"]["unresolved"], 1)
        self.assertFalse(Patient.objects.filter(no_exp="32").exists())
        self.assertEqual(unlinked_counts()["cns_legacy_consultation_record"], 1)

    def test_dry_run_no_escribe(self):
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("D1", "33", 0)])

        reporte = link_existing(dry_run=True)

        self.assertEqual(reporte["cns_legacy_consultation_record"]["rows"], 1)
        self.assertFalse(Patient.objects.filter(no_exp="33").exists())
        self.assertIsNone(LegacyConsultationRecord.objects.get(legacy_folio="D1").patient)

    def test_es_idempotente(self):
        Patient.objects.create(no_exp="34", pk_num=0)
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("E1", "34", 0)])
        link_existing()

        reporte = link_existing()

        self.assertEqual(sum(stats["rows"] for stats in reporte.values()), 0)

    def test_la_historia_clinica_ya_venia_vinculada(self):
        Patient.objects.create(no_exp="35", pk_num=0)
        ClinicalHistory.objects.create(no_exp="35", pk_num=0, patient=Patient.objects.get(no_exp="35"))

        self.assertEqual(unlinked_counts().get("cns_clinical_history", 0), 0)


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


class VincularIdPacienteCommandTests(TestCase):
    def test_informa_y_avisa_cuando_ya_se_puede_pasar_a_not_null(self):
        Patient.objects.create(no_exp="40", pk_num=0)
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("F1", "40", 0)])
        out = StringIO()

        call_command("vincular_id_paciente", stdout=out)

        texto = out.getvalue()
        self.assertIn("Filas vinculadas: 1", texto)
        self.assertIn("Todas las filas tienen paciente", texto)

    def test_sin_crear_lista_lo_que_falta(self):
        LegacyConsultationRecord.objects.bulk_create([_legacy_note("G1", "41", 0)])
        out = StringIO()

        call_command("vincular_id_paciente", "--sin-crear", stdout=out)

        self.assertIn("sin paciente en cns_legacy_consultation_record: 1", out.getvalue())
