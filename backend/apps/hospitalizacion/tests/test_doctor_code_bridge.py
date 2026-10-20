"""Puente de codigos legados de medico en hospitalizacion: el codigo legado
NUNCA es `CatMedico.id`. Ingreso y alta son `no_medico` legado ->
`LegacyMedico.medico_actual` (solo si no es NULL)."""

import datetime
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import CatTipoHospitalizacion
from apps.hospitalizacion.models import HospitalAdmission, HospitalAdmissionRevision
from apps.hospitalizacion.uses_case import hospital_admission_usecase
from apps.medicos.models import LegacyMedico
from apps.medicos.tests.factories import crear_medico

ING = "admitting_doctor_code_legacy"
ALTA = "discharge_doctor_code_legacy"


def _legado(no_medico, medico_actual=None):
    return LegacyMedico.objects.create(
        no_medico=no_medico, cd_medico=f"RH{no_medico}", sw_status="A",
        medico_actual=medico_actual,
    )


class DoctorCodeBridgeBase(TestCase):
    def setUp(self):
        self.tipo = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        # ids de SIRES elegidos para COLISIONAR con no_medico legados.
        self.m35 = crear_medico(id=35, nombre="Ana", paterno="Uno")
        self.actual = crear_medico(id=10001, nombre="Beto", paterno="Dos")
        self.otro = crear_medico(id=10002, nombre="Caro", paterno="Tres")
        _legado(512, medico_actual=self.actual)
        self._n = 0

    def _admission(self, ingreso=None, alta=None):
        self._n += 1
        return HospitalAdmission.objects.create(
            no_exp=f"EXP{self._n:04d}",
            reason="Motivo",
            admission_date=datetime.date(2026, 1, 1),
            admission_type=self.tipo,
            admitting_doctor_code_legacy=ingreso,
            discharge_doctor_code_legacy=alta,
        )


class BuildDoctorCodeLookupTests(DoctorCodeBridgeBase):
    def test_ingreso_con_ceros_resuelve_a_medico_actual(self):
        self._admission(ingreso="0512")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {"0512": 10001})

    def test_ingreso_con_espacios_resuelve(self):
        self._admission(ingreso=" 512 ")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {" 512 ": 10001})

    def test_no_medico_igual_a_cat_medico_id_no_resuelve_a_ese_medico(self):
        # CatMedico.id=35 existe, pero el legado 35 no tiene medico_actual.
        _legado(35, medico_actual=None)
        self._admission(ingreso="35")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {})

    def test_codigo_sin_legado_aunque_exista_cat_medico_id_queda_fuera(self):
        self._admission(ingreso="35")  # no hay LegacyMedico 35
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {})

    def test_legado_con_medico_actual_distinto_al_id_resuelve_al_actual(self):
        _legado(35, medico_actual=self.otro)
        self._admission(ingreso="35")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {"35": 10002})

    def test_invalidos_quedan_fuera_sin_excepcion(self):
        for raw in ("0", "00", "", "   ", "AB", "ABC", "12A", "-5", "1.5", "9999"):
            self._admission(ingreso=raw)
        self._admission(ingreso=None)
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {})

    def test_ignora_filas_con_fk_ya_resuelta(self):
        adm = self._admission(ingreso="0512")
        adm.admitting_doctor = self.actual
        adm.save()
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {})

    def test_alta_con_ceros_resuelve_a_medico_actual(self):
        self._admission(alta="0512")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ALTA), {"0512": 10001})

    def test_alta_no_medico_igual_a_cat_medico_id_sin_medico_actual_no_resuelve(self):
        _legado(35, medico_actual=None)
        self._admission(alta="35")  # CatMedico.id=35 existe, pero no es el puente
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ALTA), {})

    def test_alta_sin_legado_aunque_exista_cat_medico_id_queda_fuera(self):
        self._admission(alta="35")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ALTA), {})

    def test_alta_con_medico_actual_distinto_al_id_resuelve_al_actual(self):
        _legado(35, medico_actual=self.otro)
        self._admission(alta="35")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ALTA), {"35": 10002})

    def test_alta_invalidos_quedan_fuera(self):
        for raw in ("0", "", "   ", "AB", "12A", "-5", "1.5", "9999"):
            self._admission(alta=raw)
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ALTA), {})

    def test_cada_campo_usa_su_propio_codigo(self):
        _legado(600, medico_actual=self.otro)
        self._admission(ingreso="512", alta="600")
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ING), {"512": 10001})
        self.assertEqual(hospital_admission_usecase.build_doctor_code_lookup(ALTA), {"600": 10002})


class ResolvePendingDoctorsTests(DoctorCodeBridgeBase):
    def test_resuelve_ambos_campos_y_deja_auditoria_sin_revisiones(self):
        _legado(600, medico_actual=self.otro)
        adm = self._admission(ingreso="0512", alta="600")
        sin_match = self._admission(ingreso="9999", alta="0")

        report = hospital_admission_usecase.resolve_pending_doctors()

        adm.refresh_from_db()
        sin_match.refresh_from_db()
        self.assertEqual(adm.admitting_doctor_id, 10001)
        self.assertEqual(adm.discharge_doctor_id, 10002)
        self.assertIsNone(sin_match.admitting_doctor_id)
        self.assertIsNone(sin_match.discharge_doctor_id)
        self.assertEqual(
            report["admitting_doctor"], {"pending": 2, "resolved": 1, "unresolved": 1}
        )
        self.assertEqual(
            report["discharge_doctor"], {"pending": 2, "resolved": 1, "unresolved": 1}
        )
        self.assertEqual(
            AuditoriaEvento.objects.filter(accion="hsp_admission.resolve_pending_fk").count(), 2
        )
        self.assertEqual(HospitalAdmissionRevision.objects.count(), 0)

    def test_es_idempotente(self):
        self._admission(ingreso="0512")
        hospital_admission_usecase.resolve_pending_doctors()
        report = hospital_admission_usecase.resolve_pending_doctors()
        self.assertEqual(report["admitting_doctor"]["resolved"], 0)


class ResolveHspDoctorCodesCommandTests(DoctorCodeBridgeBase):
    def _run(self, *args):
        out = StringIO()
        call_command("resolve_hsp_doctor_codes", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_por_defecto_no_escribe_y_reporta(self):
        adm = self._admission(ingreso="0512", alta="ABC")

        output = self._run()

        adm.refresh_from_db()
        self.assertIsNone(adm.admitting_doctor_id)
        self.assertFalse(AuditoriaEvento.objects.filter(accion="hsp_admission.resolve_pending_fk").exists())
        self.assertIn("DRY-RUN", output)
        self.assertIn("pendientes=1 se resolverian=1 sin_resolver=0", output)
        self.assertIn("pendientes=1 se resolverian=0 sin_resolver=1", output)

    def test_execute_aplica_y_reporta_conteos(self):
        adm = self._admission(ingreso="0512", alta="ABC")

        output = self._run("--execute")

        adm.refresh_from_db()
        self.assertEqual(adm.admitting_doctor_id, 10001)
        self.assertIsNone(adm.discharge_doctor_id)
        self.assertIn("EJECUTADO", output)
        self.assertIn("resueltos=1 sin_resolver=0", output)
        self.assertIn("resueltos=0 sin_resolver=1", output)
