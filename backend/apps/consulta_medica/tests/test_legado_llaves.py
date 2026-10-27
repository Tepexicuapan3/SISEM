"""
Puente hacia el legado: CD_FAMILIAR de los familiares de SERMED. La copia del
legado no existe en tests: sus filas de cat_familiar se simulan.
"""
from unittest import mock

from django.test import TestCase, override_settings

from apps.consulta_medica.models import ChangeLog, Patient, PatientIdentifier
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
from apps.consulta_medica.services import legado_archivo, legado_llaves
from apps.consulta_medica.services.legado_llaves import MapaPuente

CAT_FAMILIAR = [
    {"cd_familiar": 501, "no_expf": "040041", "pk_num": 3},   # titular con ceros a la izquierda
    {"cd_familiar": 502, "no_expf": "40041", "pk_num": 4},
    {"cd_familiar": 503, "no_expf": "40041", "pk_num": 7},    # dos cd_familiar con el mismo PK_NUM
    {"cd_familiar": 504, "no_expf": "40041", "pk_num": 7},
    {"cd_familiar": 505, "no_expf": "40041", "pk_num": 0},    # sin PK_NUM
    {"cd_familiar": 506, "no_expf": "40041", "pk_num": None},
]
CON_LEGADO = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
              "legado": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}


class MapaPuenteTests(TestCase):
    def setUp(self):
        self.mapa = MapaPuente.desde_filas(CAT_FAMILIAR)

    def test_traduce_titular_y_pk_num_al_cd_familiar(self):
        self.assertEqual(self.mapa.resolver("40041", 3), (501, legado_llaves.REGISTRADO))
        self.assertEqual(self.mapa.resolver("040041", 4), (502, legado_llaves.REGISTRADO))

    def test_nunca_adivina(self):
        self.assertEqual(self.mapa.resolver("40041", 7), (None, legado_llaves.AMBIGUO))
        self.assertEqual(self.mapa.resolver("40041", 9), (None, legado_llaves.SIN_LEGADO))
        self.assertEqual(self.mapa.resolver("99999", 3), (None, legado_llaves.SIN_LEGADO))


class RegistrarCdFamiliarTests(TestCase):
    def setUp(self):
        self.mapa = MapaPuente.desde_filas(CAT_FAMILIAR)

    def _cd_familiar(self, paciente):
        return list(PatientIdentifier.objects.filter(
            patient=paciente, id_type="CD_FAMILIAR", status="A").values_list("value", flat=True))

    def test_registra_el_identificador_con_bitacora(self):
        hijo = Patient.objects.create(no_exp="40041", pk_num=3)
        self.assertEqual(legado_llaves.registrar_cd_familiar(hijo, self.mapa), legado_llaves.REGISTRADO)
        self.assertEqual(self._cd_familiar(hijo), ["501"])
        self.assertTrue(ChangeLog.objects.filter(key="CD_FAMILIAR|501", reason="LLAVE LEGADO").exists())
        # Idempotente.
        self.assertEqual(legado_llaves.registrar_cd_familiar(hijo, self.mapa), legado_llaves.YA_TENIA)

    def test_titular_y_provisional_no_aplican(self):
        titular = Patient.objects.create(no_exp="40041", pk_num=0)
        provisional = Patient.objects.create(no_exp="40041", pk_num=None, provisional_code=100000001)
        for paciente in (titular, provisional):
            self.assertEqual(legado_llaves.registrar_cd_familiar(paciente, self.mapa), legado_llaves.NO_APLICA)
        self.assertFalse(PatientIdentifier.objects.filter(id_type="CD_FAMILIAR").exists())

    def test_si_el_cd_familiar_ya_es_de_otro_paciente_no_lo_reasigna(self):
        otro = Patient.objects.create(no_exp="40041", pk_num=None, legacy_family_code=501)
        PatientIdentifier.objects.create(patient=otro, id_type="CD_FAMILIAR", value="501", created_by="u")
        hijo = Patient.objects.create(no_exp="40041", pk_num=3)
        self.assertEqual(legado_llaves.registrar_cd_familiar(hijo, self.mapa), legado_llaves.CONFLICTO)
        self.assertEqual(self._cd_familiar(hijo), [])

    def test_ambiguo_no_registra(self):
        hijo = Patient.objects.create(no_exp="40041", pk_num=7)
        self.assertEqual(legado_llaves.registrar_cd_familiar(hijo, self.mapa), legado_llaves.AMBIGUO)
        self.assertEqual(self._cd_familiar(hijo), [])


@override_settings(IDENTIDAD_PACIENTE={"VERIFICAR_SERMED": "apagado", "RECIEN_NACIDOS": False})
class PuenteAlAbrirTests(TestCase):
    def test_al_abrir_un_familiar_se_registra_despues_del_commit(self):
        filas = [f for f in CAT_FAMILIAR if f["cd_familiar"] == 501]
        with mock.patch.object(legado_archivo, "disponible", return_value=True), \
                mock.patch.object(legado_archivo, "consultar", return_value=filas) as consultar, \
                self.captureOnCommitCallbacks(execute=True):
            hijo, creado = PatientRepository.get_or_create("40041", 3)
        self.assertTrue(creado)
        self.assertTrue(PatientIdentifier.objects.filter(patient=hijo, id_type="CD_FAMILIAR", value="501").exists())
        # Solo los familiares de ese titular, no todo el cat_familiar.
        self.assertEqual(consultar.call_args[0][1], ["40041"])

    def test_sin_copia_del_legado_el_alta_sigue_normal(self):
        with self.captureOnCommitCallbacks(execute=True):
            hijo, creado = PatientRepository.get_or_create("40041", 3)
        self.assertTrue(creado)
        self.assertFalse(PatientIdentifier.objects.filter(patient=hijo, id_type="CD_FAMILIAR").exists())

    def test_si_la_copia_no_responde_el_alta_sigue_normal(self):
        with mock.patch.object(legado_archivo, "disponible", return_value=True), \
                mock.patch.object(legado_archivo, "consultar", side_effect=legado_archivo.LegadoNoDisponible("x")), \
                self.captureOnCommitCallbacks(execute=True):
            hijo, creado = PatientRepository.get_or_create("40041", 3)
        self.assertTrue(creado)
