"""
Historial previo a SIRES leido de la copia del legado: llaves por persona,
una base (año) por vez, catalogos de la base actual, medicamentos y
diagnosticos sensibles ocultos.
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
            "ds_diagnostico": diagnostico, "sw_complemento": None, "sw_status": "A", "sw_incapacidad": None, "fe_cita": None,
            "sw_laboratorio": None, "sw_gabinete": None, "sw_hospitalizacion": None,
            "no_peso": None, "no_estatura": None, "no_ta": None, "no_pulso": None, "no_temp": None,
            "no_resp": None, "no_imc": None, "no_gluc": None,
            "med_paterno": "PEREZ", "med_materno": None, "med_nombre": "ANA", "ds_clinica": "CLINICA 7",
            "cd_servicio": 22, "tp_consulta": 1, "cd_especialidad": 0,
            "ds_servicio": "SERVICIO ESPECIAL", "ds_tpconsulta": "NORMAL", "ds_especialidad": " SIN ESPECIALIDAD",
            "cd_cie": cie, "ds_cie": f"DESC {cie}" if cie else None, **kw}


class _CopiaSimulada:
    """Responde segun la consulta: esquemas, conteo por base, notas por esquema,
    diagnosticos y medicamentos."""

    def __init__(self, notas_por_esquema, diagnosticos=(), medicamentos=(), licencias=(), estudios=None):
        self.notas = notas_por_esquema
        self.diagnosticos = list(diagnosticos)
        self.medicamentos = list(medicamentos)
        self.licencias = list(licencias)
        self.estudios = estudios or {}
        self.llamadas = []

    def __call__(self, sql, params=()):
        self.llamadas.append((sql, list(params or [])))
        if "information_schema" in sql:
            return [{"table_schema": e} for e in self.notas]
        if "UNION ALL" in sql or "AS esquema" in sql:
            return [{"esquema": e, "total": len(f), "desde": min(n["fe_nota"] for n in f),
                     "hasta": max(n["fe_nota"] for n in f)} for e, f in self.notas.items() if f]
        if "det_hisnotcie" in sql:
            return self.diagnosticos
        if "det_receta" in sql:
            return self.medicamentos
        if "det_licencia" in sql:
            return self.licencias
        for detalle, filas in self.estudios.items():
            if detalle in sql:
                return filas
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

    def _correr_base(self, copia, base):
        with mock.patch.object(legado_archivo, "disponible", return_value=True),                 mock.patch.object(legado_archivo, "consultar", side_effect=copia):
            return get_patient_legacy_consultations_history("40041", 3, [ROLE_DOCTOR], [], base=base)

    def _dos_bases(self):
        return _CopiaSimulada(
            {"legado_actual": [_nota("CC25-1", date(2025, 3, 1), cie="J00")],
             "legado_2016": [_nota("CC16-9", date(2016, 5, 2)), _nota("CC16-3", date(2016, 1, 8))]},
            diagnosticos=[{"cd_snota": "CC25-1", "cd_clinica": 7, "cd_cie": "J00", "ds_cie": "RINOFARINGITIS"}],
            medicamentos=[
                {"cd_snota": "CC25-1", "no_medic": 10, "no_cantidad": 2, "ds_indicaciones": "1 CADA 8 HORAS",
                 "fe_surtida": date(2025, 3, 1), "sw_status": "A", "ds_medic": "PARACETAMOL 500 MG",
                 "ds_activo": "PARACETAMOL"},
                {"cd_snota": "CC25-1", "no_medic": 11, "no_cantidad": 1, "ds_indicaciones": None,
                 "fe_surtida": "0000-00-00", "sw_status": "B", "ds_medic": None, "ds_activo": None},
            ],
        )

    def test_sin_base_lista_las_bases_y_trae_la_mas_reciente(self):
        copia = self._dos_bases()
        payload = self._correr(copia)
        self.assertTrue(payload["disponible"])
        self.assertEqual(payload["base"], "legado_actual")
        self.assertEqual(
            payload["bases"],
            [{"sourceDb": "legado_actual", "total": 1, "from": date(2025, 3, 1), "to": date(2025, 3, 1)},
             {"sourceDb": "legado_2016", "total": 2, "from": date(2016, 1, 8), "to": date(2016, 5, 2)}],
        )
        # Solo se leen las notas de la base elegida.
        self.assertEqual([i["legacyFolio"] for i in payload["items"]], ["CC25-1"])
        self.assertFalse(any('"legado_2016"."his_notas"' in sql and "AS esquema" not in sql
                             for sql, _ in copia.llamadas))
        primera = payload["items"][0]
        self.assertEqual((primera["doctorName"], primera["clinicName"], primera["sourceDb"]),
                         ("PEREZ ANA", "CLINICA 7", "legado_actual"))
        self.assertEqual((primera["serviceName"], primera["consultationType"], primera["specialtyName"]),
                         ("SERVICIO ESPECIAL", "NORMAL", None))
        self.assertEqual(primera["diagnoses"], [{"codigo": "J00", "descripcion": "RINOFARINGITIS"}])
        self.assertEqual(primera["medications"], [
            {"name": "PARACETAMOL 500 MG", "activeIngredient": "PARACETAMOL", "quantity": 2,
             "instructions": "1 CADA 8 HORAS", "dispensedOn": date(2025, 3, 1), "cancelled": False},
            {"name": "Medicamento 11", "activeIngredient": None, "quantity": 1,
             "instructions": None, "dispensedOn": None, "cancelled": True},
        ])

    def test_con_base_trae_solo_esa_base(self):
        copia = self._dos_bases()
        payload = self._correr_base(copia, "legado_2016")
        self.assertEqual(payload["base"], "legado_2016")
        self.assertNotIn("bases", payload)
        self.assertEqual([i["legacyFolio"] for i in payload["items"]], ["CC16-9", "CC16-3"])
        self.assertEqual(payload["totalCount"], 2)
        # Por la llave del puente (expediente del titular + cd_familiar), con catalogos de la actual.
        sql_notas, params = next(l for l in copia.llamadas if '"legado_2016"."his_notas"' in l[0])
        self.assertIn('"legado_actual"."cat_medicos"', sql_notas)
        self.assertIn('"legado_actual"."cat_servicios"', sql_notas)
        self.assertEqual(params, ["40041", 501])

    def test_dias_de_incapacidad_solo_de_las_notas_marcadas(self):
        copia = _CopiaSimulada(
            {"legado_actual": [_nota("CC25-7", date(2025, 6, 2), sw_incapacidad="S"),
                               _nota("CC25-6", date(2025, 6, 1))]},
            licencias=[{"cd_snota": "CC25-7", "ds_dias": "07", "sw_status": "A"},
                       {"cd_snota": "CC25-7", "ds_dias": "3", "sw_status": "B"}],
        )
        items = self._correr(copia)["items"]
        self.assertEqual(items[0]["sickLeaves"], [{"days": 7, "cancelled": False}, {"days": 3, "cancelled": True}])
        self.assertEqual(items[1]["sickLeaves"], [])
        sql, params = next(l for l in copia.llamadas if "det_licencia" in l[0] and "information_schema" not in l[0])
        self.assertEqual(params, ["CC25-7"])

    def test_proxima_cita_de_la_nota(self):
        copia = _CopiaSimulada({"legado_actual": [_nota("HAC25-1", date(2025, 2, 24), fe_cita=date(2025, 6, 4)),
                                                  _nota("HAC25-2", date(2025, 2, 23), fe_cita="0000-00-00")]})
        items = self._correr(copia)["items"]
        self.assertEqual([i["nextAppointment"] for i in items], [date(2025, 6, 4), None])

    def test_estudios_de_los_pases_de_gabinete_y_laboratorio(self):
        copia = _CopiaSimulada(
            {"legado_actual": [_nota("TC26-2", date(2026, 1, 5), sw_gabinete="S", sw_laboratorio="S"),
                               _nota("TC26-1", date(2026, 1, 4))]},
            estudios={
                "det_pasgab": [{"cd_snota": "TC26-2", "cd_estudio": 1887, "sw_status": "A",
                                "ds_complemento": "AP Y LATERAL CON INTERPRETACION",
                                "ds_estudios": "RX ARTICULACION RODILLA (2 PROYECCIONES)"}],
                "det_paslab": [{"cd_snota": "TC26-2", "cd_estudio": 9, "sw_status": "B", "ds_complemento": " ",
                                "ds_estudios": None}],
            },
        )
        items = self._correr(copia)["items"]
        self.assertEqual(items[0]["referralStudies"], [
            {"type": "GABINETE", "name": "RX ARTICULACION RODILLA (2 PROYECCIONES)",
             "note": "AP Y LATERAL CON INTERPRETACION", "cancelled": False},
            {"type": "LABORATORIO", "name": "Estudio 9", "note": None, "cancelled": True},
        ])
        self.assertEqual(items[1]["referralStudies"], [])
        sql, params = next(l for l in copia.llamadas if "det_pasgab" in l[0] and "information_schema" not in l[0])
        self.assertIn('"legado_actual"."cat_estudios"', sql)
        self.assertEqual(params, ["TC26-2"])

    def test_pases_a_especialidad_y_a_hospital(self):
        copia = _CopiaSimulada(
            {"legado_actual": [_nota("CC14-628", date(2014, 1, 7), sw_hospitalizacion="S"),
                               _nota("CC14-600", date(2014, 1, 6))]},
            estudios={
                "pas_especialidad": [{"cd_snota": "CC14-600", "sw_status": "A", "nombre": "CARDIOLOGÍA",
                                      "clave": 5, "nota": "CONSULTA"}],
                "pas_hospital": [{"cd_snota": "CC14-628", "sw_status": "A", "nombre": "SANATORIO DURANGO",
                                  "clave": 1, "tipo": "ATENCIÓN EN URGENCIAS", "nota": "SE ENVIA PARA RX"}],
            },
        )
        items = self._correr(copia)["items"]
        self.assertEqual(items[0]["referralStudies"], [
            {"type": "HOSPITAL", "name": "SANATORIO DURANGO — ATENCIÓN EN URGENCIAS",
             "note": "SE ENVIA PARA RX", "cancelled": False},
        ])
        self.assertEqual(items[1]["referralStudies"], [
            {"type": "ESPECIALIDAD", "name": "CARDIOLOGÍA", "note": "CONSULTA", "cancelled": False},
        ])

        def llamada(tabla):
            return next(l for l in copia.llamadas if tabla in l[0] and "information_schema" not in l[0])

        # Especialidad se busca para todas las notas; hospital solo para las marcadas.
        self.assertEqual(sorted(llamada("pas_especialidad")[1]), ["CC14-600", "CC14-628"])
        self.assertEqual(llamada("pas_hospital")[1], ["CC14-628"])
        self.assertIn('"legado_actual"."cat_tphospi"', llamada("pas_hospital")[0])

    def test_sin_notas_con_incapacidad_no_consulta_licencias(self):
        copia = self._dos_bases()
        self._correr(copia)
        self.assertFalse(any(tabla in sql for sql, _ in copia.llamadas if "information_schema" not in sql
                             for tabla in ("det_licencia", "det_pasgab", "det_paslab")))

    def test_base_que_no_existe_no_lee_notas(self):
        copia = self._dos_bases()
        payload = self._correr_base(copia, "legado_1999")
        self.assertEqual((payload["items"], payload["base"]), ([], "legado_1999"))
        self.assertFalse(any("his_notas" in sql for sql, _ in copia.llamadas if "information_schema" not in sql))

    def test_sin_notas_en_ninguna_base(self):
        payload = self._correr(_CopiaSimulada({"legado_actual": []}))
        self.assertEqual((payload["items"], payload["bases"], payload["base"]), ([], [], None))

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
