"""
5.1 paso 6: sincronizacion SERMED -> PACIENTE. La replica se simula en
memoria: no se toca Oracle ni la base expedientes.
"""
import csv
import os
import tempfile
from datetime import date
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from apps.consulta_medica.models import ChangeLog, Patient, PatientIdentifier, PatientSermedState
from apps.consulta_medica.services import sermed_sync_service as sync
from apps.consulta_medica.services.sermed_source import SermedEmployee, SermedFamilyMember
from apps.consulta_medica.services.patient_identifier_service import find_patient

CURP_H = "PEGJ850315HDFRRN09"   # hombre, 15/03/1985
CURP_M = "PEGJ850315MDFRRN01"   # mujer, 15/03/1985
NACIMIENTO = date(1985, 3, 15)


def _emp(no_exp="100", **kw):
    data = dict(
        no_exp=no_exp, paternal_surname="PEREZ", maternal_surname="GOMEZ", first_name="JUAN",
        birth_date=NACIMIENTO, curp=CURP_H, sex_code="M", valid_until=date(2027, 1, 1),
        leave_date=None, leave_code=None, clinic_code="1",
    )
    data.update(kw)
    return SermedEmployee(**data)


def _fam(pk_num=501, holder="100", **kw):
    data = dict(
        pk_num=pk_num, holder_no_exp=holder, paternal_surname="PEREZ", maternal_surname="LOPEZ",
        first_name="ANA", birth_date=date(2015, 6, 1), relationship_code="H", beneficiary_type="HI",
        valid_until=date(2027, 1, 1), clinic_code="1",
    )
    data.update(kw)
    return SermedFamilyMember(**data)


class FakeSource:
    def __init__(self, employees=(), members=()):
        self._employees = {e.no_exp: e for e in employees}
        self._members = {m.pk_num: m for m in members}

    def employees(self, no_exps):
        return {n: self._employees[n] for n in no_exps if n in self._employees}

    def family_members(self, pk_nums):
        return {p: self._members[p] for p in pk_nums if p in self._members}


def _run(source, **kw):
    return sync.sync_patients(Patient.objects.order_by("id_patient"), source=source, **kw)


def _kinds(result):
    return [d.kind for d in result.discrepancies]


class TitularSyncTests(TestCase):
    def setUp(self):
        self.titular = Patient.objects.create(no_exp="100", pk_num=0)

    def test_copia_identidad_y_carga_la_curp_de_sermed(self):
        result = _run(FakeSource([_emp()]))

        self.titular.refresh_from_db()
        self.assertEqual(
            (self.titular.paternal_surname, self.titular.maternal_surname, self.titular.first_name),
            ("PEREZ", "GOMEZ", "JUAN"),
        )
        self.assertEqual(self.titular.birth_date, NACIMIENTO)
        # En SERMED M = Masculino; en SIRES H = Hombre.
        self.assertEqual(self.titular.sex, "H")
        self.assertEqual(self.titular.curp, CURP_H)
        self.assertEqual(self.titular.curp_source, Patient.CurpSource.SERMED)
        self.assertEqual(result.discrepancies, [])
        entrada = ChangeLog.objects.get(table="cns_paciente")
        self.assertEqual(entrada.reason, "SINCRONIZACION SERMED")
        self.assertEqual(entrada.user, "SYNC_SERMED")
        self.assertEqual(entrada.new_value["curp"], CURP_H)
        estado = PatientSermedState.objects.get(patient=self.titular)
        self.assertTrue(estado.found)
        self.assertEqual(estado.valid_until, date(2027, 1, 1))

    def test_sin_curp_no_carga_relleno(self):
        result = _run(FakeSource([_emp(curp="SIN CURP")]))

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.curp)
        self.assertEqual(self.titular.sex, "H")
        self.assertEqual(_kinds(result), [sync.CURP_INVALIDA])

    def test_curp_con_otra_fecha_no_se_carga_y_va_al_reporte(self):
        result = _run(FakeSource([_emp(birth_date=date(1990, 1, 1), sex_code="F")]))

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.curp)
        self.assertEqual(self.titular.sex, "M")  # el de SERMED, traducido
        self.assertEqual(_kinds(result), [sync.CURP_FECHA])

    def test_misma_fecha_y_otro_sexo_gana_la_curp(self):
        result = _run(FakeSource([_emp(curp=CURP_M, sex_code="M")]))

        self.titular.refresh_from_db()
        self.assertEqual(self.titular.curp, CURP_M)
        self.assertEqual(self.titular.sex, "M")  # M de la CURP = Mujer
        self.assertEqual(_kinds(result), [sync.SEXO_DE_CURP])

    def test_curp_de_otro_paciente_no_se_carga(self):
        Patient.objects.create(no_exp="999", pk_num=0, curp=CURP_H)

        result = _run(FakeSource([_emp()]))

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.curp)
        self.assertIn(sync.CURP_DUPLICADA, _kinds(result))

    def test_sermed_reemplaza_la_curp_capturada_del_titular(self):
        Patient.objects.filter(pk=self.titular.pk).update(curp=CURP_M, curp_source=Patient.CurpSource.CAPTURED)

        _run(FakeSource([_emp()]))

        self.titular.refresh_from_db()
        self.assertEqual((self.titular.curp, self.titular.curp_source), (CURP_H, Patient.CurpSource.SERMED))
        entrada = ChangeLog.objects.get(table="cns_paciente")
        self.assertEqual(entrada.previous_value["curp"], CURP_M)

    def test_conserva_la_curp_capturada_si_sermed_no_tiene(self):
        Patient.objects.filter(pk=self.titular.pk).update(curp=CURP_H, curp_source=Patient.CurpSource.CAPTURED)

        _run(FakeSource([_emp(curp=None)]))

        self.titular.refresh_from_db()
        self.assertEqual((self.titular.curp, self.titular.curp_source), (CURP_H, Patient.CurpSource.CAPTURED))

    def test_retira_la_curp_de_sermed_si_deja_de_ser_valida(self):
        _run(FakeSource([_emp()]))

        _run(FakeSource([_emp(birth_date=date(1990, 1, 1))]))

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.curp)
        self.assertIsNone(self.titular.curp_source)

    def test_no_toca_lo_que_captura_sires(self):
        Patient.objects.filter(pk=self.titular.pk).update(phone="5555", occupation_id=None)

        _run(FakeSource([_emp()]))

        self.titular.refresh_from_db()
        self.assertEqual(self.titular.phone, "5555")

    def test_un_cambio_de_baja_queda_en_la_bitacora(self):
        _run(FakeSource([_emp()]))

        _run(FakeSource([_emp(leave_date=date(2026, 10, 1), leave_code="R")]))

        entrada = ChangeLog.objects.get(table="cns_paciente_sermed")
        self.assertEqual(entrada.previous_value, {"leave_date": None, "leave_code": None})
        self.assertEqual(entrada.new_value, {"leave_date": "2026-10-01", "leave_code": "R"})

    def test_si_desaparece_de_sermed_se_conserva_y_se_reporta(self):
        _run(FakeSource([_emp()]))

        result = _run(FakeSource())

        self.titular.refresh_from_db()
        self.assertEqual(self.titular.first_name, "JUAN")
        self.assertFalse(PatientSermedState.objects.get(patient=self.titular).found)
        self.assertEqual(_kinds(result), [sync.NO_ENCONTRADO])

    def test_es_idempotente(self):
        _run(FakeSource([_emp()]))
        entradas = ChangeLog.objects.count()

        result = _run(FakeSource([_emp()]))

        self.assertEqual(ChangeLog.objects.count(), entradas)
        self.assertNotIn("pacientes_actualizados", result.counts)

    def test_dry_run_no_escribe(self):
        result = _run(FakeSource([_emp()]), dry_run=True)

        self.titular.refresh_from_db()
        self.assertIsNone(self.titular.first_name)
        self.assertEqual(result.counts["pacientes_actualizados"], 1)
        self.assertFalse(PatientSermedState.objects.exists())
        self.assertFalse(ChangeLog.objects.exists())


class FamilySyncTests(TestCase):
    def test_copia_identidad_y_registra_su_pk_num(self):
        familiar = Patient.objects.create(no_exp="100", pk_num=501)

        result = _run(FakeSource(members=[_fam()]))

        familiar.refresh_from_db()
        self.assertEqual(familiar.first_name, "ANA")
        self.assertEqual(familiar.birth_date, date(2015, 6, 1))
        self.assertEqual(find_patient(PatientIdentifier.IdType.PK_NUM, 501), familiar)
        estado = PatientSermedState.objects.get(patient=familiar)
        self.assertEqual((estado.holder_no_exp, estado.relationship_code), ("100", "H"))
        self.assertEqual(result.counts["pk_num_registrados"], 1)

    def test_cambio_de_titular_se_reporta_sin_crear_otro_paciente(self):
        familiar = Patient.objects.create(no_exp="100", pk_num=501)

        result = _run(FakeSource(members=[_fam(holder="200")]))

        self.assertEqual(_kinds(result), [sync.CAMBIO_TITULAR])
        self.assertEqual(Patient.objects.count(), 1)
        self.assertEqual(PatientSermedState.objects.get(patient=familiar).holder_no_exp, "200")

    def test_familiar_solo_del_legado_no_se_busca_en_sermed(self):
        Patient.objects.create(no_exp="100", pk_num=None, legacy_family_code=33)

        result = _run(FakeSource())

        self.assertEqual(result.counts, {"familiares_solo_legado": 1})


class SincronizarPacientesCommandTests(TestCase):
    def test_reporte_de_discrepancias(self):
        Patient.objects.create(no_exp="100", pk_num=0)
        Patient.objects.create(no_exp="200", pk_num=0)
        fd, ruta = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        self.addCleanup(os.remove, ruta)
        out = StringIO()

        with patch.object(sync, "ReplicaSermedSource", return_value=FakeSource([_emp(curp="SIN CURP")])):
            call_command("sincronizar_pacientes_sermed", "--reporte", ruta, stdout=out)

        self.assertIn("procesados=2", out.getvalue())
        with open(ruta, encoding="utf-8") as fh:
            tipos = sorted(fila[0] for fila in list(csv.reader(fh))[1:])
        self.assertEqual(tipos, [sync.CURP_INVALIDA, sync.NO_ENCONTRADO])

    def test_solo_un_expediente(self):
        Patient.objects.create(no_exp="100", pk_num=0)
        Patient.objects.create(no_exp="200", pk_num=0)
        out = StringIO()

        with patch.object(sync, "ReplicaSermedSource", return_value=FakeSource([_emp()])):
            call_command("sincronizar_pacientes_sermed", "--no-exp", "100", stdout=out)

        self.assertIn("procesados=1", out.getvalue())
        self.assertEqual(Patient.objects.get(no_exp="100").first_name, "JUAN")
        self.assertIsNone(Patient.objects.get(no_exp="200").first_name)


class ActualizarExpedienteHookTests(TestCase):
    _BASE = "apps.administracion.use_cases.expedientes.actualizar_expediente"

    def _replica_simulada(self):
        """La conexion 'expedientes' no existe en tests: candado y transaccion
        de la replica se reemplazan por contextos vacios."""
        from contextlib import nullcontext

        return [
            patch(f"{self._BASE}.obtener_conexion_oracle", return_value=MagicMock()),
            patch(f"{self._BASE}.sincronizar_tabla", return_value={"insertados": 0, "eliminados": 0, "actualizados": 0}),
            patch(f"{self._BASE}.candado_expediente", side_effect=lambda _exp: nullcontext(True)),
            patch(f"{self._BASE}._transaccion_replica", side_effect=nullcontext),
        ]

    def test_actualizar_expediente_sincroniza_sus_pacientes(self):
        from apps.administracion.use_cases.expedientes.actualizar_expediente import actualizar_expediente

        Patient.objects.create(no_exp="100", pk_num=0)
        mocks = self._replica_simulada()
        for m in mocks:
            m.start()
        self.addCleanup(lambda: [m.stop() for m in mocks])
        with patch.object(sync, "ReplicaSermedSource", return_value=FakeSource([_emp()])):
            resultado = actualizar_expediente("100")

        self.assertEqual(resultado["estado"], "OK")
        self.assertEqual(resultado["pacientes"]["procesados"], 1)
        self.assertEqual(Patient.objects.get(no_exp="100").first_name, "JUAN")

    def test_si_falla_la_sincronizacion_de_pacientes_el_resultado_es_parcial(self):
        from apps.administracion.use_cases.expedientes.actualizar_expediente import actualizar_expediente

        mocks = self._replica_simulada()
        for m in mocks:
            m.start()
        self.addCleanup(lambda: [m.stop() for m in mocks])
        with patch.object(sync, "sync_no_exp", side_effect=RuntimeError("replica caida")):
            resultado = actualizar_expediente("100")

        self.assertEqual(resultado["estado"], "PARCIAL")
        self.assertTrue(any("replica caida" in e for e in resultado["errores"]))
        self.assertEqual(resultado["tablas"]["cat_empleados"], {"insertados": 0, "eliminados": 0, "actualizados": 0})
