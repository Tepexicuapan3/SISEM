"""
5.2: ANTECEDENTE_PERSONAL / ANTECEDENTE_FAMILIAR.sw_presente. "Niega diabetes"
es un dato clinico distinto de "no se pregunto" (que no tiene registro).
"""
from rest_framework import status

from apps.consulta_medica.models import FamilyHistory, PersonalHistory, Presence
from apps.consulta_medica.tests.test_unified_history import _UnifiedApiBase


class PersonalHistoryPresenceTests(_UnifiedApiBase):
    def test_por_defecto_lo_tiene(self):
        created = self._post(self._url("personal-history"), {"description": "Diabetes mellitus"})

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["presence"], "S")

    def test_registra_que_lo_niega(self):
        created = self._post(
            self._url("personal-history"), {"cieCode": "A090", "presence": "N"},
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["presence"], "N")
        self.assertEqual(PersonalHistory.objects.get().presence, Presence.DENIED)

    def test_lo_niega_no_lleva_fecha_de_diagnostico(self):
        response = self._post(
            self._url("personal-history"),
            {"description": "Asma", "presence": "N", "diagnosisDate": "2020-01-01"},
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("diagnosisDate", response.data["details"])
        self.assertFalse(PersonalHistory.objects.exists())

    def test_la_regla_aplica_tambien_al_editar_solo_un_campo(self):
        created = self._post(
            self._url("personal-history"), {"description": "Asma", "diagnosisDate": "2020-01-01"},
        )

        response = self._patch(self._url(f"personal-history/{created.data['id']}"), {"presence": "N"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(PersonalHistory.objects.get().presence, Presence.PRESENT)

    def test_pasar_a_niega_quitando_la_fecha(self):
        created = self._post(
            self._url("personal-history"), {"description": "Asma", "diagnosisDate": "2020-01-01"},
        )

        response = self._patch(
            self._url(f"personal-history/{created.data['id']}"), {"presence": "N", "diagnosisDate": None},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["presence"], "N")

    def test_valor_invalido_se_rechaza(self):
        response = self._post(self._url("personal-history"), {"description": "Asma", "presence": "X"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)


class FamilyHistoryPresenceTests(_UnifiedApiBase):
    def test_registra_que_lo_niega(self):
        created = self._post(
            self._url("family-history"), {"description": "Cancer", "presence": "N"},
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["presence"], "N")
        self.assertEqual(FamilyHistory.objects.get().presence, Presence.DENIED)

    def test_lo_niega_no_lleva_finado(self):
        response = self._post(
            self._url("family-history"),
            {"description": "Cancer", "presence": "N", "isDeceased": True},
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("isDeceased", response.data["details"])

    def test_lo_niega_necesita_el_padecimiento_no_solo_la_causa_de_muerte(self):
        response = self._post(
            self._url("family-history"), {"presence": "N", "causeOfDeath": "Infarto"},
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertFalse(FamilyHistory.objects.exists())

    def test_lo_tiene_sigue_aceptando_solo_causa_de_muerte(self):
        response = self._post(
            self._url("family-history"), {"isDeceased": True, "causeOfDeath": "Infarto"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["presence"], "S")
