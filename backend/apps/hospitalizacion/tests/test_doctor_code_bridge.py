"""Puente de codigos legados de medico en hospitalizacion (R8, S8.1-S8.3):
`int(codigo) == CatMedico.id`, lookup, use-case y management command."""

import datetime
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import CatTipoHospitalizacion
from apps.hospitalizacion.models import HospitalAdmission, HospitalAdmissionRevision
from apps.hospitalizacion.uses_case import hospital_admission_usecase
from apps.medicos.models import CatMedico


class DoctorCodeBridgeBase(TestCase):
    def setUp(self):
        self.tipo = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        self.m35 = CatMedico.objects.create(id=35, nombre="Ana", paterno="Uno")
        self.m512 = CatMedico.objects.create(id=512, nombre="Beto", paterno="Dos")
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
    def test_codigo_con_ceros_a_la_izquierda_se_resuelve(self):  # S8.1
        self._admission(ingreso="0512")
        lookup = hospital_admission_usecase.build_doctor_code_lookup("admitting_doctor_code_legacy")
        self.assertEqual(lookup, {"0512": 512})

    def test_codigo_simple_se_resuelve(self):  # S8.1
        self._admission(ingreso="35")
        lookup = hospital_admission_usecase.build_doctor_code_lookup("admitting_doctor_code_legacy")
        self.assertEqual(lookup, {"35": 35})

    def test_invalidos_quedan_fuera_sin_excepcion(self):  # S8.2
        for raw in ("0", "00", "", "   ", "ABC", "12A", "-5", "1.5"):
            self._admission(ingreso=raw)
        self._admission(ingreso=None)
        lookup = hospital_admission_usecase.build_doctor_code_lookup("admitting_doctor_code_legacy")
        self.assertEqual(lookup, {})

    def test_numerico_sin_medico_existente_queda_fuera(self):  # S8.3
        self._admission(ingreso="9999")
        lookup = hospital_admission_usecase.build_doctor_code_lookup("admitting_doctor_code_legacy")
        self.assertEqual(lookup, {})

    def test_ignora_filas_con_fk_ya_resuelta(self):
        adm = self._admission(ingreso="0512")
        adm.admitting_doctor = self.m512
        adm.save()
        lookup = hospital_admission_usecase.build_doctor_code_lookup("admitting_doctor_code_legacy")
        self.assertEqual(lookup, {})

    def test_cada_campo_usa_su_propio_codigo(self):
        self._admission(ingreso="35", alta="512")
        self.assertEqual(
            hospital_admission_usecase.build_doctor_code_lookup("admitting_doctor_code_legacy"),
            {"35": 35},
        )
        self.assertEqual(
            hospital_admission_usecase.build_doctor_code_lookup("discharge_doctor_code_legacy"),
            {"512": 512},
        )


class ResolvePendingDoctorsTests(DoctorCodeBridgeBase):
    def test_resuelve_ambos_campos_y_deja_auditoria_sin_revisiones(self):
        adm = self._admission(ingreso="0512", alta="35")
        sin_match = self._admission(ingreso="9999", alta="0")

        report = hospital_admission_usecase.resolve_pending_doctors()

        adm.refresh_from_db()
        sin_match.refresh_from_db()
        self.assertEqual(adm.admitting_doctor_id, 512)
        self.assertEqual(adm.discharge_doctor_id, 35)
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
        self.assertEqual(adm.admitting_doctor_id, 512)
        self.assertIsNone(adm.discharge_doctor_id)
        self.assertIn("EJECUTADO", output)
        self.assertIn("resueltos=1 sin_resolver=0", output)
        self.assertIn("resueltos=0 sin_resolver=1", output)
