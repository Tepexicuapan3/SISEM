"""
Bloque C0 del plan contraer la llave vieja: la unica conversion de lo que
manda la pantalla (expediente del titular + pkNum) al registro del paciente.
"""
from django.test import TestCase, override_settings

from apps.consulta_medica.models import Patient, ProvisionalPatient
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave, registros_de_la_persona

APAGADO = override_settings(IDENTIDAD_PACIENTE={"VERIFICAR_SERMED": "apagado", "RECIEN_NACIDOS": False})


@APAGADO
class PacienteDeLlaveTests(TestCase):
    def test_titular_y_familiar_se_abren_por_la_puerta_central(self):
        titular = paciente_de_llave("40041", 0)
        hijo = paciente_de_llave("40041", 3)
        self.assertEqual((titular.no_exp, titular.pk_num), ("40041", 0))
        self.assertEqual((hijo.no_exp, hijo.pk_num), ("40041", 3))
        # La segunda vez es el mismo registro, nunca un duplicado.
        self.assertEqual(paciente_de_llave("40041", 3), hijo)

    def test_normaliza_el_expediente(self):
        self.assertEqual(paciente_de_llave("040041", 0), paciente_de_llave("40041", 0))
        self.assertEqual(Patient.objects.filter(pk_num=0).count(), 1)

    def test_provisional_se_encuentra_por_su_cd_provisional(self):
        bebe = Patient.objects.create(no_exp="40041", pk_num=None, provisional_code=100000001)
        ProvisionalPatient.objects.create(patient=bebe, holder_no_exp="40041", valid_until="2026-12-31")
        self.assertEqual(paciente_de_llave("40041", 100000001), bebe)

    def test_una_clave_provisional_desconocida_nunca_crea_un_paciente(self):
        self.assertIsNone(paciente_de_llave("40041", 100000099))
        self.assertFalse(Patient.objects.filter(pk_num=100000099).exists())

    def test_familiar_del_legado_sin_pk_num_por_su_cd_familiar(self):
        legado = Patient.objects.create(no_exp="40041", pk_num=None, legacy_family_code=52895)
        self.assertEqual(paciente_de_llave("40041", 52895), legado)

    def test_sin_crear_solo_busca(self):
        self.assertIsNone(paciente_de_llave("40041", 7, crear=False))
        self.assertFalse(Patient.objects.exists())

    def test_sin_llave_no_hay_paciente(self):
        self.assertIsNone(paciente_de_llave("", 0))
        self.assertIsNone(paciente_de_llave("40041", None))

    def test_registros_de_la_persona_junta_sus_afiliaciones(self):
        bebe = Patient.objects.create(no_exp="40041", pk_num=None, provisional_code=100000001)
        hijo = paciente_de_llave("40041", 3)
        Patient.objects.filter(pk=hijo.pk).update(person_id=bebe.person_id)
        self.assertEqual(registros_de_la_persona(bebe), [bebe, hijo])
