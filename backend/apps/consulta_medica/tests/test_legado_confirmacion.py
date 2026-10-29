"""
Confirmar por seccion los datos del legado (paso 3 del diseño del 2026-10-27).
La copia del legado no existe en tests: his_clinica y his_clinicad se simulan.
"""
from datetime import date
from unittest import mock

from django.test import TestCase

from apps.catalogos.models import CatHabito
from apps.consulta_medica.models import (
    Allergy,
    FamilyHistory,
    Habit,
    LegacyReview,
    Patient,
    PatientIdentifier,
    PersonalHistory,
    SpecialtySource,
)
from apps.consulta_medica.services import legado_archivo, legado_confirmacion as lc
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave

HIS_CLINICA = [{"no_hisclin": 11, "fe_hisclin": date(2024, 2, 1), "ds_alergias": "PENICILINA, SULFAS; NEGADAS"}]
HIS_CLINICAD = [{
    "no_hisclin": 21, "fe_hisclin": date(2023, 1, 5), "no_exp": "40041", "tp_paciente": 501,
    "ds_alemedicam": "AMOXICILINA", "ds_alemdental": "", "sw_diabetesp": "S", "sw_presaltap": "N",
    "sw_cancer": "S", "ds_muerte": "", "ds_antquir": "APENDICECTOMIA", "sw_tabaquismo": "S",
    "ds_habitos": "", "ds_alimentos": "",
}]


class _Copia:
    def __init__(self, clinica=HIS_CLINICA, clinicad=HIS_CLINICAD):
        self.tablas = {"his_clinica": clinica, "his_clinicad": clinicad}

    def __call__(self, sql, params=()):
        if "information_schema" in sql:
            return [{"table_schema": "legado_actual"}] if params[0] in self.tablas else []
        for tabla, filas in self.tablas.items():
            if f'"legado_actual"."{tabla}"' in sql:
                return [dict(f) for f in filas]
        return []


class ConfirmacionTests(TestCase):
    def setUp(self):
        for codigo in ("tabaquismo", "alcoholismo", "toxicomanias", "otro", "alimentacion"):
            CatHabito.objects.get_or_create(code=codigo, defaults={"name": codigo})
        self.hijo = Patient.objects.create(no_exp="40041", pk_num=3)
        PatientIdentifier.objects.create(patient=self.hijo, id_type="CD_FAMILIAR", value="501", created_by="u")
        self.copia = _Copia()

    def _con_copia(self):
        return mock.patch.multiple(legado_archivo, disponible=mock.Mock(return_value=True),
                                   consultar=mock.Mock(side_effect=self.copia))

    def _secciones(self):
        with self._con_copia():
            return {s["seccion"]: s for s in lc.propuestas("40041", 3)}

    def test_propone_por_seccion_sin_respuestas_negativas(self):
        secciones = self._secciones()
        self.assertEqual([i["texto"] for i in secciones[lc.ALERGIAS]["items"]],
                         ["PENICILINA", "SULFAS", "AMOXICILINA"])
        self.assertEqual([i["texto"] for i in secciones[lc.PERSONALES]["items"]], ["Diabetes mellitus"])
        self.assertEqual([i["texto"] for i in secciones[lc.FAMILIARES]["items"]], ["Cancer"])
        self.assertEqual([i["texto"] for i in secciones[lc.QUIRURGICOS]["items"]], ["APENDICECTOMIA"])
        self.assertEqual([i["texto"] for i in secciones[lc.HABITOS]["items"]], ["Tabaquismo"])
        self.assertTrue(secciones[lc.ALERGIAS]["items"][0]["ref"].startswith("legado_actual:his_clinica:11:"))

    def test_confirma_lo_marcado_descarta_lo_demas_y_no_lo_vuelve_a_ofrecer(self):
        alergias = self._secciones()[lc.ALERGIAS]["items"]
        aceptar = [alergias[0]["ref"], alergias[2]["ref"]]  # PENICILINA y AMOXICILINA, no SULFAS
        with self._con_copia():
            resultado = lc.confirmar("40041", 3, lc.ALERGIAS, aceptar, user_id=99)
        self.assertEqual(resultado, {"confirmados": 2, "descartados": 1})
        self.assertEqual(set(Allergy.objects.filter(patient=self.hijo).values_list("substance", flat=True)),
                         {"PENICILINA", "AMOXICILINA"})
        self.assertEqual(Allergy.objects.get(substance="PENICILINA").created_by_id, 99)
        self.assertEqual(LegacyReview.objects.get(text="SULFAS").decision, "R")
        self.assertNotIn(lc.ALERGIAS, self._secciones())

    def test_confirma_antecedentes_y_habitos_con_origen_legado(self):
        secciones = self._secciones()
        with self._con_copia():
            for seccion in (lc.PERSONALES, lc.FAMILIARES, lc.HABITOS):
                lc.confirmar("40041", 3, seccion, [i["ref"] for i in secciones[seccion]["items"]], user_id=99)
        personal = PersonalHistory.objects.get(patient=self.hijo)
        self.assertEqual((personal.description, personal.source), ("Diabetes mellitus", SpecialtySource.LEGACY))
        self.assertTrue(personal.legacy_ref.startswith("legado_actual:his_clinicad:21:"))
        self.assertTrue(FamilyHistory.objects.filter(patient=self.hijo, description="Cancer").exists())
        self.assertTrue(Habit.objects.filter(patient=self.hijo, habit__code="tabaquismo").exists())
        self.assertEqual(LegacyReview.objects.filter(decision="C").count(), 3)

    def test_no_crea_lo_que_no_propuso(self):
        with self._con_copia(), self.assertRaises(VisitDomainError) as error:
            lc.confirmar("40041", 3, lc.ALERGIAS, ["legado_actual:his_clinica:999:ds_alergias:0"])
        self.assertEqual(error.exception.code, "LEGADO_CAMBIO")
        self.assertFalse(Allergy.objects.exists())

    def test_lo_capturado_en_sires_no_se_propone(self):
        Allergy.objects.create(patient=_paciente_de_llave("40041", 3), allergy_type_id=9, substance="penicilina",
                               severity=Allergy.Severity.MODERATE, service_origin_code=1)
        textos = [i["texto"] for i in self._secciones()[lc.ALERGIAS]["items"]]
        self.assertNotIn("PENICILINA", textos)

    def test_el_mismo_dato_en_otra_fila_tampoco_vuelve(self):
        otra = dict(HIS_CLINICAD[0], no_hisclin=22, fe_hisclin=date(2020, 1, 1))
        self.copia = _Copia(clinicad=HIS_CLINICAD + [otra])
        personales = self._secciones()[lc.PERSONALES]["items"]
        self.assertEqual(len(personales), 1)  # sin repetidos: gana la fila mas reciente
        with self._con_copia():
            lc.confirmar("40041", 3, lc.PERSONALES, [personales[0]["ref"]])
        self.assertNotIn(lc.PERSONALES, self._secciones())

    def test_sin_llaves_del_legado_no_hay_nada_que_revisar(self):
        provisional = Patient.objects.create(no_exp="40041", pk_num=None, provisional_code=100000001)
        with self._con_copia():
            self.assertEqual(lc.propuestas("40041", provisional.provisional_code), [])

    def test_alergias_para_la_receta_sin_copia_o_si_no_responde_no_frenan(self):
        self.assertEqual(lc.alergias_sin_confirmar("40041", 3), [])
        with mock.patch.multiple(legado_archivo, disponible=mock.Mock(return_value=True),
                                 consultar=mock.Mock(side_effect=legado_archivo.LegadoNoDisponible("x"))):
            self.assertEqual(lc.alergias_sin_confirmar("40041", 3), [])
        with self._con_copia():
            self.assertEqual([i["texto"] for i in lc.alergias_sin_confirmar("40041", 3)],
                             ["PENICILINA", "SULFAS", "AMOXICILINA"])
