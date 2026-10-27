"""
Historial previo a SIRES leido de la copia del legado: llaves por persona,
todas las bases, catalogos de la base actual y diagnosticos sensibles ocultos.
La copia no existe en tests: sus respuestas se simulan por consulta.
"""
from datetime import date
from unittest import mock

from django.test import TestCase

from apps.catalogos.models import SensitiveCieRange
from apps.catalogos.services.sensitive_diagnosis_service import invalidate_cache
from apps.consulta_medica.models import Patient, PatientIdentifier
from apps.consulta_medica.services import legado_archivo, legado_historial
from apps.consulta_medica.uses_case.consultation_usecase import ROLE_DOCTOR
from apps.consulta_medica.uses_case.patient_history_usecase import get_patient_legacy_consultations_history


def _identificador(paciente, tipo, valor):
    PatientIdentifier.objects.create(patient=paciente, id_type=tipo, value=str(valor), created_by="u")


def _nota(folio, fecha, cie=None, diagnostico=None, **kw):
    return {"cd_snota": folio, "cd_clinica": 7, "fe_nota": fecha, "hh_nota": "10:00", "cd_medico": "12",
            "ds_sintomas": "TOS", "ds_objetivo": None, "ds_analisis": None, "ds_plan": None,
            "ds_diagnostico": diagnostico, "sw_complemento": None, "sw_status": "A",
            "no_peso": None, "no_estatura": None, "no_ta": None, "no_pulso": None, "no_temp": None,
            "no_resp": None, "no_imc": None, "no_gluc": None,
            "med_paterno": "PEREZ", "med_materno": None, "med_nombre": "ANA", "ds_clinica": "CLINICA 7",
            "cd_cie": cie, "ds_cie": f"DESC {cie}" if cie else None, **kw}


class _CopiaSimulada:
    """Responde segun la consulta: esquemas, notas por esquema y diagnosticos."""

    def __init__(self, notas_por_esquema, diagnosticos=()):
        self.notas = notas_por_esquema
        self.diagnosticos = list(diagnosticos)
        self.llamadas = []

    def __call__(self, sql, params=()):
        self.llamadas.append((sql, list(params or [])))
        if "information_schema" in sql:
            return [{"table_schema": e} for e in self.notas]
        if "det_hisnotcie" in sql:
            return self.diagnosticos
        for esquema, filas in self.notas.items():
            if f'"{esquema}"."his_notas"' in sql:
                return filas
        return []


class LlavesLegadoTests(TestCase):
    def test_titular_y_familiar_de_la_misma_persona(self):
        titular = Patient.objects.create(no_exp="40041", pk_num=0)
        _identificador(titular, "NO_EXP", "40041")
        hijo = Patient.objects.create(no_exp="40041", pk_num=3)
        _identificador(hijo, "PK_NUM", 3)
        _identificador(hijo, "CD_FAMILIAR", 501)
        # El hijo, ya trabajador, es la misma persona que un titular de otro expediente.
        como_trabajador = Patient.objects.create(no_exp="77001", pk_num=0)
        _identificador(como_trabajador, "NO_EXP", "77001")
        Patient.objects.filter(pk=como_trabajador.pk).update(person_id=hijo.person_id)

        self.assertEqual(legado_historial.llaves_legado("40041", 3), [("40041", 501), ("77001", 0)])
        self.assertEqual(legado_historial.llaves_legado("40041", 0), [("40041", 0)])

    def test_provisional_o_sin_puente_no_tiene_llaves(self):
        Patient.objects.create(no_exp="40041", pk_num=None, provisional_code=100000001)
        Patient.objects.create(no_exp="40041", pk_num=9)
        self.assertEqual(legado_historial.llaves_legado("40041", 100000001), [])
        self.assertEqual(legado_historial.llaves_legado("40041", 9), [])


class HistorialTests(TestCase):
    def setUp(self):
        self.hijo = Patient.objects.create(no_exp="40041", pk_num=3)
        _identificador(self.hijo, "CD_FAMILIAR", 501)
        SensitiveCieRange.objects.create(code_prefix_start="B20", code_prefix_end="B24",
                                         category="hiv", required_permission="clinico:diagnosticos_vih:read")
        invalidate_cache()

    def tearDown(self):
        invalidate_cache()

    def _correr(self, copia, permissions=()):
        with mock.patch.object(legado_archivo, "disponible", return_value=True), \
                mock.patch.object(legado_archivo, "consultar", side_effect=copia):
            return get_patient_legacy_consultations_history("40041", 3, [ROLE_DOCTOR], list(permissions))

    def test_junta_todas_las_bases_con_catalogos_de_la_actual(self):
        copia = _CopiaSimulada(
            {"legado_actual": [_nota("CC25-1", date(2025, 3, 1), cie="J00")],
             "legado_2016": [_nota("CC16-9", date(2016, 5, 2))]},
            diagnosticos=[{"cd_snota": "CC25-1", "cd_clinica": 7, "cd_cie": "J00", "ds_cie": "RINOFARINGITIS"}],
        )
        payload = self._correr(copia)
        self.assertTrue(payload["disponible"])
        self.assertEqual([i["legacyFolio"] for i in payload["items"]], ["CC25-1", "CC16-9"])
        primera = payload["items"][0]
        self.assertEqual((primera["doctorName"], primera["clinicName"], primera["sourceDb"]),
                         ("PEREZ ANA", "CLINICA 7", "legado_actual"))
        self.assertEqual(primera["diagnoses"], [{"codigo": "J00", "descripcion": "RINOFARINGITIS"}])
        # Por la llave del puente (expediente del titular + cd_familiar), con catalogos de la actual.
        sql_notas, params = next(l for l in copia.llamadas if '"legado_2016"."his_notas"' in l[0])
        self.assertIn('"legado_actual"."cat_medicos"', sql_notas)
        self.assertEqual(params, ["40041", 501])

    def test_oculta_el_diagnostico_sensible_sin_permiso(self):
        copia = _CopiaSimulada({"legado_actual": [_nota("CC25-2", date(2025, 4, 1), cie="B24",
                                                        diagnostico="VIH EN CONTROL")]})
        item = self._correr(copia)["items"][0]
        self.assertTrue(item["diagnosisRestricted"])
        self.assertIsNone(item["primaryCie"]["codigo"])
        self.assertNotIn("VIH", item["diagnosticImpression"])

        item = self._correr(copia, permissions=["clinico:diagnosticos_vih:read"])["items"][0]
        self.assertFalse(item["diagnosisRestricted"])
        self.assertEqual(item["primaryCie"]["codigo"], "B24")

    def test_si_la_copia_no_responde_lo_dice(self):
        with mock.patch.object(legado_archivo, "disponible", return_value=True), \
                mock.patch.object(legado_archivo, "consultar", side_effect=legado_archivo.LegadoNoDisponible("x")):
            payload = get_patient_legacy_consultations_history("40041", 3, [ROLE_DOCTOR], [])
        self.assertFalse(payload["disponible"])
        self.assertEqual(payload["items"], [])

    def test_sin_copia_configurada_usa_el_archivo_migrado(self):
        payload = get_patient_legacy_consultations_history("40041", 3, [ROLE_DOCTOR], [])
        self.assertNotIn("disponible", payload)
        self.assertEqual(payload["items"], [])
