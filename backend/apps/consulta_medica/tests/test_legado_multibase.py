"""
Plan identidad del paciente, bloque D: el legado se trae de varias bases
(dbclinicas actual y las anuales dbclinicas2015...dbclinicas2024_a). Nada de
una base puede sobrescribir lo de otra:
  - diagnosticos: cd_detcie se reinicia en cada base -> llave (base, cd_detcie);
  - notas: el folio (CC25-1) incluye el anio y sigue siendo unico; el mismo
    folio desde OTRA base no se sobrescribe, va al reporte;
  - las filas importadas antes de registrar el origen se adoptan, no se duplican.
"""
from datetime import date
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from apps.consulta_medica.models import LegacyConsultationDiagnosis, LegacyConsultationRecord
from apps.consulta_medica.services.legacy_family_map import LegacyFamilyMap

CONECTAR = "apps.authentication.management.commands._legacy_mysql_base.pymysql.connect"
MAPA = "apps.consulta_medica.management.commands.migrar_notas_clinicas_legacy.LegacyFamilyMap.from_legacy_connection"


def _conexion(filas):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = filas
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn


def _nota(folio, no_exp=100, sintomas="Tos"):
    return {"cd_snota": folio, "no_exp": no_exp, "tp_paciente": "0", "fe_nota": date(2016, 5, 2),
            "hh_nota": "10:00", "cd_medico": "M1", "cd_clinica": 1, "ds_sintomas": sintomas}


def _diagnostico(cd_detcie, folio, cie=1234):
    return {"cd_detcie": cd_detcie, "cd_snota": folio, "cd_cie": cie, "cd_medico": "M1",
            "cd_clinica": 1, "sw_status": "A"}


class _Migrar:
    def _correr(self, comando, filas, base, *extra):
        salida = StringIO()
        with patch(CONECTAR, return_value=_conexion(filas)), \
             patch(MAPA, return_value=LegacyFamilyMap.from_rows([])):
            call_command(comando, *extra, host="x", user="x", password="x", database=base, stdout=salida)
        return salida.getvalue()


class NotasMultibaseTests(_Migrar, TestCase):
    def test_guarda_la_base_de_origen(self):
        self._correr("migrar_notas_clinicas_legacy", [_nota("CC16-1")], "dbclinicas2016")
        self.assertEqual(LegacyConsultationRecord.objects.get().legacy_source_db, "dbclinicas2016")

    def test_repetir_la_misma_base_actualiza_sin_duplicar(self):
        self._correr("migrar_notas_clinicas_legacy", [_nota("CC16-1", sintomas="Tos")], "dbclinicas2016")
        self._correr("migrar_notas_clinicas_legacy", [_nota("CC16-1", sintomas="Fiebre")], "dbclinicas2016")
        nota = LegacyConsultationRecord.objects.get()
        self.assertEqual(nota.subjective, "Fiebre")

    def test_el_mismo_folio_desde_otra_base_no_se_sobrescribe(self):
        self._correr("migrar_notas_clinicas_legacy", [_nota("CC24-1", sintomas="Original")], "dbclinicas2024_a")
        salida = self._correr("migrar_notas_clinicas_legacy", [_nota("CC24-1", sintomas="Otra")], "dbclinicas2024_b")
        nota = LegacyConsultationRecord.objects.get()
        self.assertEqual((nota.subjective, nota.legacy_source_db), ("Original", "dbclinicas2024_a"))
        self.assertIn("no se sobrescribe", salida)

    def test_el_simulacro_cuenta_los_conflictos(self):
        self._correr("migrar_notas_clinicas_legacy", [_nota("CC24-1")], "dbclinicas2024_a")
        salida = self._correr("migrar_notas_clinicas_legacy", [_nota("CC24-1"), _nota("CC24-2")],
                              "dbclinicas2024_b", "--dry-run")
        self.assertIn("Creados: 1", salida)
        self.assertIn("Conflictos de folio (no se sobrescriben): 1", salida)

    def test_una_nota_importada_sin_origen_se_adopta(self):
        # Importada antes de que existiera db_origen.
        LegacyConsultationRecord.objects.create(legacy_folio="CC25-1", no_exp="100", pk_num=0,
                                                consultation_date=date(2025, 1, 2))
        self._correr("migrar_notas_clinicas_legacy", [_nota("CC25-1")], "dbclinicas")
        self.assertEqual(LegacyConsultationRecord.objects.count(), 1)
        self.assertEqual(LegacyConsultationRecord.objects.get().legacy_source_db, "dbclinicas")


class DiagnosticosMultibaseTests(_Migrar, TestCase):
    def test_el_mismo_cd_detcie_de_dos_bases_no_se_pisa(self):
        self._correr("migrar_diagnosticos_cie_legacy", [_diagnostico(5, "CC16-9", cie=111)], "dbclinicas2016")
        self._correr("migrar_diagnosticos_cie_legacy", [_diagnostico(5, "CC25-3", cie=222)], "dbclinicas")
        filas = dict(LegacyConsultationDiagnosis.objects.values_list("legacy_source_db", "cie_code_legacy"))
        self.assertEqual(filas, {"dbclinicas2016": 111, "dbclinicas": 222})

    def test_repetir_la_misma_base_actualiza(self):
        self._correr("migrar_diagnosticos_cie_legacy", [_diagnostico(5, "CC16-9", cie=111)], "dbclinicas2016")
        self._correr("migrar_diagnosticos_cie_legacy", [_diagnostico(5, "CC16-9", cie=333)], "dbclinicas2016")
        self.assertEqual(LegacyConsultationDiagnosis.objects.get().cie_code_legacy, 333)

    def test_un_diagnostico_sin_origen_se_adopta_si_es_el_mismo(self):
        LegacyConsultationDiagnosis.objects.create(legacy_id=5, legacy_folio="CC25-3", cie_code_legacy=1234)
        self._correr("migrar_diagnosticos_cie_legacy", [_diagnostico(5, "CC25-3")], "dbclinicas")
        self.assertEqual(list(LegacyConsultationDiagnosis.objects.values_list("legacy_source_db", flat=True)),
                         ["dbclinicas"])

    def test_sin_origen_con_otro_folio_es_de_otra_base_y_se_conserva(self):
        LegacyConsultationDiagnosis.objects.create(legacy_id=5, legacy_folio="CC25-3", cie_code_legacy=111)
        self._correr("migrar_diagnosticos_cie_legacy", [_diagnostico(5, "CC16-9", cie=222)], "dbclinicas2016")
        self.assertEqual(LegacyConsultationDiagnosis.objects.count(), 2)


class MapaFamiliaresOtraBaseTests(TestCase):
    """Las bases anuales traducen tp_paciente con el cat_familiar actual."""

    def test_lee_cat_familiar_de_la_base_indicada(self):
        conn = _conexion([{"cd_familiar": 9, "no_expf": 100, "pk_num": 48411}])
        LegacyFamilyMap.from_legacy_connection(conn, "dbclinicas")
        consulta = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
        self.assertIn("`dbclinicas`.cat_familiar", consulta)

    def test_sin_base_usa_la_misma_conexion(self):
        conn = _conexion([])
        LegacyFamilyMap.from_legacy_connection(conn)
        consulta = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
        self.assertEqual(consulta, "SELECT cd_familiar, no_expf, pk_num FROM cat_familiar")

    def test_rechaza_un_nombre_de_base_invalido(self):
        with self.assertRaises(ValueError):
            LegacyFamilyMap.from_legacy_connection(_conexion([]), "x; DROP TABLE y")
