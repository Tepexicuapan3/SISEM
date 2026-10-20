"""Runbook de reset de TEST (R10): command `reset_catalogo_medicos`.

Guard de --db-name, dry-run por defecto, abort sin --purge-citas-cirugias,
FKs nuleadas con `*_code_legacy` intactos y totales invariantes."""

import datetime
import unittest
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.almacen_insumos.models import Almacen, ConsumoConsulta
from apps.catalogos.models import (
    CatCentroAtencion,
    CatClasificacionCirugia,
    CatTipoCirugia,
    CatTipoHospitalizacion,
)
from apps.cirugias.models import SurgerySchedule
from apps.hospitalizacion.models import HospitalAdmission, HospitalAdmissionRevision
from apps.medicos.models import CatMedico, RelMedicoCentro
from apps.medicos.tests.factories import crear_medico
from apps.recepcion.models import CitaMedica, HorarioDisponible


class ResetCatalogoMedicosTests(TestCase):
    def setUp(self):
        self.db_name = str(connection.settings_dict["NAME"])
        self.m1 = crear_medico(id=10, nombre="Ana", paterno="Uno")
        self.m2 = crear_medico(id=20, nombre="Beto", paterno="Dos")

        self.centro = CatCentroAtencion.objects.create(
            name="Centro Reset", code="RST-001",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        RelMedicoCentro.objects.create(
            medico=self.m1, centro=self.centro, fecha_inicio=datetime.date(2026, 1, 1),
        )
        HorarioDisponible.objects.create(
            medico=self.m1, fecha=datetime.date(2026, 1, 5), hora=datetime.time(9, 0),
        )

        tipo = CatTipoHospitalizacion.objects.create(name="HOSPITALIZACIÓN", legacy_code=4)
        self.adm = HospitalAdmission.objects.create(
            no_exp="EXP0001", reason="Motivo", admission_date=datetime.date(2026, 1, 1),
            admission_type=tipo,
            admitting_doctor=self.m1, admitting_doctor_code_legacy="0010",
            discharge_doctor=self.m2, discharge_doctor_code_legacy="20",
        )
        self.rev = HospitalAdmissionRevision.objects.create(
            admission=self.adm,
            previous_admitting_doctor=self.m1, previous_discharge_doctor=self.m2,
            change_reason="Prueba",
        )
        almacen = Almacen.objects.create(nombre="Almacen Reset", id_centro_atencion=self.centro)
        self.consumo = ConsumoConsulta.objects.create(
            id_almacen=almacen, medico=self.m1, fch_consumo=datetime.date(2026, 1, 2),
        )

    def _run(self, **kwargs):
        out = StringIO()
        kwargs.setdefault("db_name", self.db_name)
        call_command("reset_catalogo_medicos", stdout=out, **kwargs)
        return out.getvalue()

    def _crear_cita(self):
        return CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), no_exp="40041", pk_num=0,
            medico=self.m1, fecha_hora=timezone.now() + datetime.timedelta(days=1),
        )

    def _crear_cirugia(self):
        return SurgerySchedule.objects.create(
            folio="CIR-RST-1", no_exp="EXP-R1", pk_num=0, surgeon=self.m2,
            surgery_type=CatTipoCirugia.objects.create(name="Apendicectomia"),
            classification=CatClasificacionCirugia.objects.create(name="Corta"),
            scheduled_date=datetime.date(2026, 2, 1), scheduled_time=datetime.time(10, 0),
        )

    # -- guardas ----------------------------------------------------------

    def test_db_name_es_obligatorio(self):
        with self.assertRaises(CommandError):
            call_command("reset_catalogo_medicos", stdout=StringIO())

    def test_db_name_incorrecto_aborta_sin_tocar_nada(self):
        with self.assertRaisesMessage(CommandError, "no coincide"):
            self._run(db_name="otra_bd", execute=True)
        self.assertEqual(CatMedico.objects.count(), 2)
        self.adm.refresh_from_db()
        self.assertEqual(self.adm.admitting_doctor_id, 10)

    def test_dry_run_no_cambia_nada_e_imprime_conteos(self):
        salida = self._run()
        self.assertIn("DRY-RUN", salida)
        self.assertIn("cat_medicos: 2", salida)
        self.assertEqual(CatMedico.objects.count(), 2)
        self.assertEqual(RelMedicoCentro.objects.count(), 1)
        self.adm.refresh_from_db()
        self.rev.refresh_from_db()
        self.consumo.refresh_from_db()
        self.assertEqual(self.adm.admitting_doctor_id, 10)
        self.assertEqual(self.rev.previous_admitting_doctor_id, 10)
        self.assertEqual(self.consumo.medico_id, 10)

    def test_dry_run_con_citas_advierte_pero_no_falla(self):
        self._crear_cita()
        salida = self._run()
        self.assertIn("abortaria", salida)
        self.assertEqual(CitaMedica.objects.count(), 1)

    # -- citas / cirugias --------------------------------------------------

    def test_aborta_con_citas_sin_flag(self):
        self._crear_cita()
        with self.assertRaisesMessage(CommandError, "--purge-citas-cirugias"):
            self._run(execute=True)
        self.assertEqual(CatMedico.objects.count(), 2)
        self.assertEqual(CitaMedica.objects.count(), 1)
        self.adm.refresh_from_db()
        self.assertEqual(self.adm.admitting_doctor_id, 10)

    def test_aborta_con_cirugias_sin_flag(self):
        self._crear_cirugia()
        with self.assertRaisesMessage(CommandError, "--purge-citas-cirugias"):
            self._run(execute=True)
        self.assertEqual(SurgerySchedule.objects.count(), 1)
        self.assertEqual(CatMedico.objects.count(), 2)

    def test_con_flag_purga_citas_y_cirugias_por_orm(self):
        self._crear_cita()
        self._crear_cirugia()
        salida = self._run(execute=True, purge_citas_cirugias=True)
        self.assertEqual(CitaMedica.objects.count(), 0)
        self.assertEqual(SurgerySchedule.objects.count(), 0)
        self.assertEqual(CatMedico.objects.count(), 0)
        self.assertIn("citas_medicas=1 cir_surgery=1", salida)

    # -- ejecucion ---------------------------------------------------------

    def test_execute_vacia_catalogo_y_cascadea_rel_y_slots(self):
        salida = self._run(execute=True)
        self.assertIn("EJECUTADO", salida)
        self.assertEqual(CatMedico.objects.count(), 0)
        self.assertEqual(RelMedicoCentro.objects.count(), 0)
        self.assertEqual(HorarioDisponible.objects.count(), 0)

    def test_execute_nulea_fks_y_conserva_code_legacy(self):
        self._run(execute=True)
        self.adm.refresh_from_db()
        self.rev.refresh_from_db()
        self.consumo.refresh_from_db()
        self.assertIsNone(self.adm.admitting_doctor_id)
        self.assertIsNone(self.adm.discharge_doctor_id)
        self.assertEqual(self.adm.admitting_doctor_code_legacy, "0010")
        self.assertEqual(self.adm.discharge_doctor_code_legacy, "20")
        self.assertIsNone(self.rev.previous_admitting_doctor_id)
        self.assertIsNone(self.rev.previous_discharge_doctor_id)
        self.assertIsNone(self.consumo.medico_id)

    def test_execute_conserva_totales_de_admisiones_revisiones_y_consumos(self):
        self._run(execute=True)
        self.assertEqual(HospitalAdmission.objects.count(), 1)
        self.assertEqual(HospitalAdmissionRevision.objects.count(), 1)
        self.assertEqual(ConsumoConsulta.objects.count(), 1)

    def test_salida_incluye_conteos_antes_despues_y_siguientes_pasos(self):
        salida = self._run(execute=True)
        self.assertIn("Conteos ANTES", salida)
        self.assertIn("Conteos DESPUES", salida)
        self.assertIn("hsp_admission (con medico ingreso/alta): 1", salida)
        self.assertIn("resolve_hsp_doctor_codes", salida)
        self.assertIn("id_usuario IS NULL", salida)

    def test_catalogo_vacio_es_idempotente(self):
        self._run(execute=True)
        self._run(execute=True)
        self.assertEqual(CatMedico.objects.count(), 0)

    # -- secuencia --------------------------------------------------------

    def test_seq_start_por_defecto_10000_en_el_plan(self):
        salida = self._run()
        self.assertIn("max(10000, MAX(id)+1)", salida)

    def test_seq_start_personalizado_en_el_plan(self):
        salida = self._run(seq_start=50000)
        self.assertIn("max(50000, MAX(id)+1)", salida)

    def test_seq_start_invalido_aborta(self):
        with self.assertRaisesMessage(CommandError, "--seq-start"):
            self._run(seq_start=0, execute=True)
        self.assertEqual(CatMedico.objects.count(), 2)

    @unittest.skipUnless(connection.vendor == "postgresql", "setval solo en PostgreSQL")
    def test_execute_deja_la_secuencia_en_10000_nunca_en_1(self):
        salida = self._run(execute=True)
        self.assertIn("proximo nextval = 10000", salida)
        nuevo = crear_medico(nombre="Nuevo", paterno="Medico")
        self.assertEqual(nuevo.id, 10000)

    @unittest.skipUnless(connection.vendor == "postgresql", "setval solo en PostgreSQL")
    def test_execute_respeta_seq_start_mayor(self):
        salida = self._run(execute=True, seq_start=20000)
        self.assertIn("proximo nextval = 20000", salida)
