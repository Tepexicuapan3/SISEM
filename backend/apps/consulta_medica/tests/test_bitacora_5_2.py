"""
5.2 paso 4: las modificaciones y bajas de los datos clinicos permanentes van a
cns_bitacora_cambios (documento: "modificaciones y bajas se registran
siempre"). Editar solo el estado es ACTUALIZACION; cualquier otro campo es
CORRECCION; la baja lleva "BAJA: <motivo>" y no guarda valor nuevo.
"""
from rest_framework import status

from apps.catalogos.models import CatHabito
from apps.consulta_medica.models import ChangeLog
from apps.consulta_medica.services.change_log_service import deactivation_reason, edit_reason
from apps.consulta_medica.tests.test_unified_history import _UnifiedApiBase


def _log(table):
    return ChangeLog.objects.filter(table=table)


class ReasonRulesTests(_UnifiedApiBase):
    def test_solo_estado_es_actualizacion_lo_demas_correccion(self):
        self.assertEqual(
            edit_reason({"status": "A", "x": 1}, {"status": "R", "x": 1}, evolution_fields=("status",)),
            ChangeLog.Reason.CLINICAL_UPDATE,
        )
        self.assertEqual(
            edit_reason({"status": "A", "x": 1}, {"status": "R", "x": 2}, evolution_fields=("status",)),
            ChangeLog.Reason.CORRECTION,
        )

    def test_motivo_de_baja_acotado_a_60(self):
        self.assertEqual(deactivation_reason(None), "BAJA")
        self.assertEqual(deactivation_reason("  Duplicado "), "BAJA: Duplicado")
        self.assertEqual(len(deactivation_reason("x" * 200)), 60)


class PersonalHistoryLogTests(_UnifiedApiBase):
    def setUp(self):
        super().setUp()
        self.record = self._post(self._url("personal-history"), {"description": "Asma", "status": "A"}).data

    def test_alta_no_va_a_la_bitacora(self):
        # El alta ya queda en usr_alta/fch_alta (regla 3 del documento).
        self.assertFalse(_log("cns_antecedente_personal").exists())

    def test_resolver_es_actualizacion(self):
        self._patch(self._url(f"personal-history/{self.record['id']}"), {"status": "R"})

        entrada = _log("cns_antecedente_personal").get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.CLINICAL_UPDATE)
        self.assertEqual(entrada.key, f"id_antecedente|{self.record['id']}")
        self.assertEqual((entrada.previous_value, entrada.new_value), ({"status": "A"}, {"status": "R"}))
        self.assertEqual(entrada.user, str(self.doctor_user.id_usuario))

    def test_cambiar_la_descripcion_es_correccion(self):
        self._patch(self._url(f"personal-history/{self.record['id']}"), {"description": "Asma bronquial"})

        entrada = _log("cns_antecedente_personal").get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.CORRECTION)
        self.assertEqual(entrada.new_value, {"description": "Asma bronquial"})

    def test_guardar_sin_cambios_no_registra(self):
        self._patch(self._url(f"personal-history/{self.record['id']}"), {"description": "Asma"})

        self.assertFalse(_log("cns_antecedente_personal").exists())

    def test_baja_registra_el_motivo_sin_valor_nuevo(self):
        self._delete(self._url(f"personal-history/{self.record['id']}"), {"reason": "Era de otro paciente"})

        entrada = _log("cns_antecedente_personal").get()
        self.assertEqual(entrada.action, ChangeLog.Action.DELETE)
        self.assertEqual(entrada.reason, "BAJA: Era de otro paciente")
        self.assertIsNone(entrada.new_value)
        self.assertEqual(entrada.previous_value["description"], "Asma")
        self.assertTrue(entrada.previous_value["is_active"])


class OtherRecordsLogTests(_UnifiedApiBase):
    def test_familiar_y_quirurgico_se_registran_en_su_tabla(self):
        family = self._post(self._url("family-history"), {"description": "Diabetes"}).data
        surgical = self._post(self._url("surgical-history"), {"procedure": "Apendicectomia"}).data

        self._patch(self._url(f"family-history/{family['id']}"), {"description": "Diabetes tipo 2"})
        self._delete(self._url(f"surgical-history/{surgical['id']}"), {"reason": "Duplicado"})

        self.assertEqual(_log("cns_antecedente_familiar").get().reason, ChangeLog.Reason.CORRECTION)
        self.assertEqual(_log("cns_antecedente_quirurgico").get().action, ChangeLog.Action.DELETE)

    def test_baja_de_habito_se_registra(self):
        habit = self._post(self._url("habits"), {"habitId": CatHabito.objects.get(code="tabaquismo").id}).data

        self._delete(self._url(f"habits/{habit['id']}"), {"reason": "Capturado por error"})

        entrada = _log("cns_habito").get()
        self.assertEqual((entrada.action, entrada.reason), (ChangeLog.Action.DELETE, "BAJA: Capturado por error"))

    def test_tratamiento_dental_queda_fuera_de_la_5_2(self):
        treatment = self._post(self._url("dental-treatments"), {"toothFdi": "16", "procedure": "Resina"}).data

        self._patch(self._url(f"dental-treatments/{treatment['id']}"), {"procedure": "Amalgama"})

        self.assertFalse(ChangeLog.objects.filter(table__startswith="cns_tratamiento").exists())


class AllergyLogTests(_UnifiedApiBase):
    def setUp(self):
        super().setUp()
        self.allergy = self._post(
            self._url("allergies"), {"allergyTypeId": 1, "substance": "Penicilina", "severity": "G"},
        ).data

    def test_editar_la_alergia_es_correccion(self):
        response = self._patch(self._url(f"allergies/{self.allergy['id']}"), {"substance": "Amoxicilina"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entrada = _log("cns_allergy").get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.CORRECTION)
        self.assertEqual(entrada.key, f"id_alergia|{self.allergy['id']}")
        self.assertEqual(
            (entrada.previous_value, entrada.new_value), ({"substance": "Penicilina"}, {"substance": "Amoxicilina"}),
        )

    def test_resolverla_es_actualizacion_con_motivo(self):
        self._post(self._url(f"allergies/{self.allergy['id']}/status"), {"status": "R", "reason": "Desensibilizado"})

        entrada = _log("cns_allergy").get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.CLINICAL_UPDATE)
        self.assertEqual(entrada.new_value, {"status": "R", "motivo": "Desensibilizado"})

    def test_capturada_por_error_es_correccion(self):
        self._post(self._url(f"allergies/{self.allergy['id']}/status"), {"status": "E", "reason": "No era alergia"})

        entrada = _log("cns_allergy").get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.CORRECTION)
        self.assertEqual(entrada.new_value["is_active"], False)

    def test_baja_del_endpoint_anterior(self):
        response = self._delete(self._url(f"allergies/{self.allergy['id']}"), {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entrada = _log("cns_allergy").get()
        self.assertEqual((entrada.action, entrada.reason), (ChangeLog.Action.DELETE, "BAJA"))
