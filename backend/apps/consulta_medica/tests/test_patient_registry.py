"""
Plan identidad del paciente, Fase 1: el alta de un registro de paciente pasa
por PatientRepository.get_or_create, que normaliza el no_exp y verifica en
SERMED segun IDENTIDAD_PACIENTE["VERIFICAR_SERMED"] (apagado / observar /
bloquear). La replica de SERMED no existe en tests: existe_en_sermed se simula.
"""
from unittest import mock

from django.test import TestCase, override_settings

from apps.administracion.models import AuditoriaEvento
from apps.consulta_medica.models import ClinicalHistory, Patient
from apps.consulta_medica.repositories.clinical_history_repository import (
    ClinicalHistoryRepository,
    PatientRepository,
)
from apps.consulta_medica.services import patient_registry_service as registro
from apps.consulta_medica.services.patient_link_service import link_existing
from apps.recepcion.services.errors import VisitDomainError

EXISTE = "apps.consulta_medica.services.patient_registry_service.existe_en_sermed"


def _modo(valor):
    return override_settings(IDENTIDAD_PACIENTE={
        "VERIFICAR_SERMED": valor, "LECTURA_OPERATIVA_POR_ID": False,
        "RECIEN_NACIDOS": False, "VINCULACION": False,
    })


class NormalizarNoExpTests(TestCase):
    def test_quita_espacios_y_ceros_a_la_izquierda(self):
        self.assertEqual(registro.normalizar_no_exp(" 040041 "), "40041")
        self.assertEqual(registro.normalizar_no_exp(40041), "40041")
        self.assertEqual(registro.normalizar_no_exp("0"), "0")

    def test_lo_que_no_es_numerico_solo_se_recorta(self):
        self.assertEqual(registro.normalizar_no_exp(" T00ab "), "T00ab")

    def test_no_nace_un_segundo_registro_por_un_espacio_o_un_cero(self):
        primero, creado = PatientRepository.get_or_create("40041", 900)
        segundo, creado2 = PatientRepository.get_or_create(" 040041", 900)
        self.assertTrue(creado)
        self.assertFalse(creado2)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(Patient.objects.filter(pk_num=900).count(), 1)

    def test_usa_el_registro_anterior_guardado_sin_normalizar(self):
        # Dato previo a la Fase 1 con cero a la izquierda: no se duplica.
        anterior = Patient.objects.create(no_exp="040041", pk_num=901)
        paciente, creado = PatientRepository.get_or_create("040041", 901)
        self.assertFalse(creado)
        self.assertEqual(paciente.pk, anterior.pk)

    def test_la_historia_usa_el_no_exp_guardado_en_el_paciente(self):
        historia, _ = ClinicalHistoryRepository.get_or_create_for_patient(" 040041", 902)
        # Plan contraer la llave vieja: la cabecera ya no guarda la llave; la del paciente, normalizada.
        self.assertIsNone(historia.no_exp)
        self.assertEqual(historia.patient.no_exp, "40041")


class VerificarSermedTests(TestCase):
    @_modo("apagado")
    def test_apagado_no_consulta_sermed(self):
        with mock.patch(EXISTE) as existe:
            PatientRepository.get_or_create("100", 0)
        existe.assert_not_called()
        self.assertTrue(Patient.objects.filter(no_exp="100").exists())

    @_modo("observar")
    def test_observar_crea_igual_y_deja_constancia(self):
        with mock.patch(EXISTE, return_value=False):
            paciente, creado = PatientRepository.get_or_create("100", 900, created_by_id=None)
        self.assertTrue(creado)
        evento = AuditoriaEvento.objects.get(accion=registro.ACCION_OBSERVADA)
        self.assertEqual(evento.codigo_error, "PATIENT_NOT_IN_SERMED")
        self.assertEqual(evento.meta, {"noExp": "100", "pkNum": 900, "origen": "ATENCION", "modo": "observar"})

    @_modo("observar")
    def test_observar_sin_constancia_si_existe_en_sermed(self):
        with mock.patch(EXISTE, return_value=True):
            PatientRepository.get_or_create("100", 900)
        self.assertFalse(AuditoriaEvento.objects.filter(accion=registro.ACCION_OBSERVADA).exists())

    @_modo("bloquear")
    def test_bloquear_no_crea_si_sermed_confirma_que_no_existe(self):
        with mock.patch(EXISTE, return_value=False), self.assertRaises(VisitDomainError) as error:
            PatientRepository.get_or_create("100", 900)
        self.assertEqual(error.exception.code, "PATIENT_NOT_IN_SERMED")
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(Patient.objects.filter(no_exp="100").exists())

    @_modo("bloquear")
    def test_bloquear_no_bloquea_si_sermed_no_responde(self):
        with mock.patch(EXISTE, return_value=None):
            _, creado = PatientRepository.get_or_create("100", 900)
        self.assertTrue(creado)

    @_modo("bloquear")
    def test_bloquear_no_aplica_a_un_paciente_que_ya_existe(self):
        Patient.objects.create(no_exp="100", pk_num=900)
        with mock.patch(EXISTE, return_value=False) as existe:
            _, creado = PatientRepository.get_or_create("100", 900)
        self.assertFalse(creado)
        existe.assert_not_called()

    @_modo("bloquear")
    def test_bloquear_no_aplica_al_legado_ni_a_la_regularizacion(self):
        with mock.patch(EXISTE, return_value=False) as existe:
            ClinicalHistoryRepository.get_or_create_for_patient("100", 0, origen=registro.ORIGEN_LEGADO)
            PatientRepository.get_or_create("200", 0, origen=registro.ORIGEN_REGULARIZACION)
        existe.assert_not_called()
        self.assertEqual(Patient.objects.filter(no_exp__in=["100", "200"]).count(), 2)

    @_modo("bloquear")
    def test_bloquear_en_la_historia_clinica_tampoco_crea_la_cabecera(self):
        with mock.patch(EXISTE, return_value=False), self.assertRaises(VisitDomainError):
            ClinicalHistoryRepository.get_or_create_for_patient("100", 900)
        self.assertFalse(ClinicalHistory.objects.exists())

    @_modo("bloquear")
    def test_vincular_id_paciente_regulariza_sin_consultar_sermed(self):
        from apps.consulta_medica.models import Allergy

        # Fila clinica sin paciente (como antes de la etapa 7b).
        Allergy.objects.create(
            no_exp="300", pk_num=0, allergy_type_id=9, substance="PENICILINA",
            severity="M", service_origin_code=1,
        )
        with mock.patch(EXISTE, return_value=False) as existe:
            link_existing()
        existe.assert_not_called()
        self.assertTrue(Patient.objects.filter(no_exp="300", pk_num=0).exists())
