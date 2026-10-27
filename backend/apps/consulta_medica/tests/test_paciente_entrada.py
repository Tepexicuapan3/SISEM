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


@APAGADO
class SerializersConIdPacienteTests(TestCase):
    """C1, etapa A: crear ficha y cita aceptan idPaciente (y la llave vieja, transitorio)."""

    def _cita(self, **datos):
        from apps.recepcion.views.citas_views import CreateCitaSerializer

        return CreateCitaSerializer(data={"medicoId": 1, "fechaHora": "2026-11-03T10:00:00", **datos})

    def _ficha(self, **datos):
        from apps.recepcion.serializers import CreateVisitSerializer

        return CreateVisitSerializer(data={"arrivalType": "walk_in", **datos})

    def test_con_id_paciente_se_completa_la_llave_desde_cns_paciente(self):
        hijo = paciente_de_llave("40041", 3)
        for serializer in (self._cita(idPaciente=hijo.pk), self._ficha(idPaciente=hijo.pk)):
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual((serializer.validated_data["noExp"], serializer.validated_data["pkNum"]), ("40041", 3))

    def test_el_provisional_se_manda_por_id_paciente(self):
        bebe = Patient.objects.create(no_exp="40041", pk_num=None, provisional_code=100000001)
        serializer = self._ficha(idPaciente=bebe.pk)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["pkNum"], 100000001)

    def test_sin_paciente_o_con_uno_que_no_existe_es_error(self):
        sin_paciente = self._cita()
        self.assertFalse(sin_paciente.is_valid())
        self.assertIn("idPaciente", sin_paciente.errors)
        serializer = self._ficha(idPaciente=999999)
        self.assertFalse(serializer.is_valid())
        self.assertIn("idPaciente", serializer.errors)

    def test_la_llave_vieja_sigue_funcionando_mientras_dura_la_transicion(self):
        serializer = self._cita(noExp="40041", pkNum=0)
        self.assertTrue(serializer.is_valid(), serializer.errors)
