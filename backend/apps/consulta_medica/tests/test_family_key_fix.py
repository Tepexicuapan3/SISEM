"""
Correccion del bug CD_FAMILIAR (documento "Historia Clinica Unificada", 5.1 y 8):
el tp_paciente del legado es cat_familiar.cd_familiar, no el PK_NUM de SERMED.
"""
import csv
import os
import tempfile
from datetime import date
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.consulta_medica.models import (
    Allergy,
    ChangeLog,
    ClinicalHistory,
    LegacyConsultationRecord,
    Patient,
    PatientIdentifier,
)
from apps.consulta_medica.repositories.clinical_history_repository import ClinicalHistoryRepository
from apps.consulta_medica.services import family_key_fix_service as fix
from apps.consulta_medica.services.legacy_family_map import LegacyFamilyMap
from apps.consulta_medica.services.patient_identifier_service import find_patient

IdType = PatientIdentifier.IdType

# cat_familiar del legado: (cd_familiar, no_expf, pk_num)
LEGACY_ROWS = [
    (1, "100", 501),     # traducible
    (2, "100", None),    # sin PK_NUM
    (3, "100", 0),       # PK_NUM 0 = del trabajador: no se traduce
    (4, "100", 900),     # PK_NUM repetido...
    (5, "100", 900),     # ...en dos cd_familiar
    (6, "100", 7),       # el PK_NUM 7 de este familiar...
    (7, "100", 600),     # ...es el cd_familiar de este otro
    (8, "200", 800),     # familiar de otro titular
]


def _map():
    return LegacyFamilyMap.from_rows(LEGACY_ROWS)


class LegacyFamilyMapTests(SimpleTestCase):
    def test_traduce_solo_pk_num_validos_y_unicos(self):
        fmap = _map()

        self.assertEqual(fmap.pk_by_cd[1], 501)
        self.assertNotIn(2, fmap.pk_by_cd)
        self.assertNotIn(3, fmap.pk_by_cd)
        self.assertEqual(fmap.ambiguous_cds, {4, 5})

    def test_acepta_filas_de_dictcursor(self):
        fmap = LegacyFamilyMap.from_rows([{"cd_familiar": 1, "no_expf": 100, "pk_num": 501}])

        self.assertEqual(fmap.titular_by_cd[1], "100")
        self.assertEqual(fmap.pk_by_cd[1], 501)

    def test_llave_de_registro_del_legado(self):
        fmap = _map()

        self.assertEqual(fmap.record_key("100", 0), (0, None))
        self.assertEqual(fmap.record_key("100", 1), (501, 1))
        # Sin PK_NUM: conserva el cd_familiar como llave.
        self.assertEqual(fmap.record_key("100", 2), (2, 2))
        self.assertEqual(fmap.record_key("100", 4), (4, 4))
        # cd_familiar de otro titular: no se traduce.
        self.assertEqual(fmap.record_key("100", 8), (8, 8))


class ClassifyTests(SimpleTestCase):
    def test_clasifica_cada_caso(self):
        fmap = _map()
        casos = {
            1: fix.LEGACY_TO_PK, 2: fix.LEGACY_NO_PK, 3: fix.LEGACY_NO_PK,
            4: fix.AMBIGUOUS_MAP, 7: fix.AMBIGUOUS, 8: fix.OTHER_TITULAR,
            501: fix.NATIVE, 999: fix.UNKNOWN,
        }
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(fix.classify("100", valor, fmap).kind, esperado)
        self.assertEqual(fix.classify("100", 1, fmap).target_pk, 501)


class RunFixTests(TestCase):
    def _bug(self, pk_num, folio):
        """Lo que dejaron los comandos migrar_*_legacy: cd_familiar como pk_num."""
        ClinicalHistoryRepository.get_or_create_for_patient("100", pk_num)
        Allergy.objects.create(
            no_exp="100", pk_num=pk_num, allergy_type_id=1, substance=f"Sustancia {folio}",
            service_origin_code=Allergy.SERVICE_BY_SOURCE[Allergy.Source.GENERAL],
        )
        LegacyConsultationRecord.objects.create(
            legacy_folio=folio, no_exp="100", pk_num=pk_num, consultation_date=date(2020, 1, 1),
        )

    def test_mueve_todo_al_pk_num_real_y_registra_identificadores(self):
        self._bug(1, "F1")

        resultado = fix.run_fix(_map())

        self.assertEqual(resultado["counts"], {fix.LEGACY_TO_PK: 1})
        self.assertFalse(Allergy.objects.filter(no_exp="100", pk_num=1).exists())
        self.assertTrue(Allergy.objects.filter(no_exp="100", pk_num=501).exists())
        self.assertEqual(LegacyConsultationRecord.objects.get(legacy_folio="F1").pk_num, 501)
        self.assertEqual(ClinicalHistory.objects.get(no_exp="100").pk_num, 501)
        paciente = Patient.objects.get(no_exp="100", pk_num=501)
        self.assertEqual(paciente.legacy_family_code, 1)
        self.assertEqual(find_patient(IdType.PK_NUM, 501), paciente)
        self.assertEqual(find_patient(IdType.CD_FAMILIAR, 1), paciente)
        entrada = ChangeLog.objects.get(reason=ChangeLog.Reason.LEGACY_KEY_FIX)
        self.assertEqual(entrada.previous_value["pk_num"], 1)
        self.assertEqual(entrada.new_value, {"pk_num": 501, "cd_familiar": 1})

    def test_familiar_sin_pk_num_queda_identificado_por_cd_familiar(self):
        self._bug(2, "F2")

        fix.run_fix(_map())

        paciente = Patient.objects.get(no_exp="100", legacy_family_code=2)
        self.assertIsNone(paciente.pk_num)
        self.assertEqual(find_patient(IdType.CD_FAMILIAR, 2), paciente)
        # Los registros conservan el cd_familiar como llave hasta el paso 7.
        self.assertTrue(Allergy.objects.filter(no_exp="100", pk_num=2).exists())
        # Volver a abrir su historia no crea un paciente duplicado.
        historia, _ = ClinicalHistoryRepository.get_or_create_for_patient("100", 2)
        self.assertEqual(historia.patient, paciente)
        self.assertEqual(Patient.objects.filter(no_exp="100").count(), 1)

    def test_pk_num_cero_del_legado_no_se_mezcla_con_el_titular(self):
        self._bug(3, "F3")

        fix.run_fix(_map())

        paciente = Patient.objects.get(no_exp="100", legacy_family_code=3)
        self.assertIsNone(paciente.pk_num)
        self.assertFalse(Patient.objects.filter(no_exp="100", pk_num=0).exists())

    def test_casos_dudosos_van_a_revision_sin_tocar_nada(self):
        for valor, folio in ((4, "F4"), (7, "F7"), (8, "F8"), (999, "F9")):
            self._bug(valor, folio)

        resultado = fix.run_fix(_map())

        tipos = {d.kind for d in resultado["review"]}
        self.assertEqual(tipos, {fix.AMBIGUOUS_MAP, fix.AMBIGUOUS, fix.OTHER_TITULAR, fix.UNKNOWN})
        self.assertEqual(
            set(Patient.objects.values_list("pk_num", flat=True)), {4, 7, 8, 999},
        )
        self.assertFalse(PatientIdentifier.objects.exists())

    def test_si_el_familiar_ya_existe_con_su_pk_num_hace_falta_fusionar(self):
        self._bug(1, "F1")
        ClinicalHistoryRepository.get_or_create_for_patient("100", 501)  # abierto en SIRES

        resultado = fix.run_fix(_map())

        fusion = [d for d in resultado["review"] if d.kind == fix.MERGE_NEEDED]
        self.assertEqual(len(fusion), 1)
        self.assertEqual(fusion[0].value, 1)
        self.assertTrue(Allergy.objects.filter(no_exp="100", pk_num=1).exists())

    def test_familiar_ya_correcto_solo_registra_su_pk_num(self):
        ClinicalHistoryRepository.get_or_create_for_patient("100", 501)

        resultado = fix.run_fix(_map())

        self.assertEqual(resultado["counts"], {fix.NATIVE: 1})
        self.assertEqual(find_patient(IdType.PK_NUM, 501).pk_num, 501)

    def test_es_idempotente(self):
        self._bug(1, "F1")
        self._bug(2, "F2")
        fix.run_fix(_map())
        entradas = ChangeLog.objects.count()

        resultado = fix.run_fix(_map())

        self.assertEqual(resultado["moved"], {})
        self.assertEqual(ChangeLog.objects.count(), entradas)
        self.assertEqual(Patient.objects.filter(no_exp="100").count(), 2)

    def test_dry_run_no_escribe(self):
        self._bug(1, "F1")

        resultado = fix.run_fix(_map(), dry_run=True)

        self.assertEqual(resultado["counts"], {fix.LEGACY_TO_PK: 1})
        self.assertTrue(Allergy.objects.filter(no_exp="100", pk_num=1).exists())
        self.assertFalse(PatientIdentifier.objects.exists())


class CorregirLlaveFamiliaresCommandTests(TestCase):
    def _legacy_conn(self):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = LEGACY_ROWS
        conn.cursor.return_value.__enter__.return_value = cursor
        return conn

    def test_reporta_y_escribe_el_csv_de_revision(self):
        ClinicalHistoryRepository.get_or_create_for_patient("100", 1)
        ClinicalHistoryRepository.get_or_create_for_patient("100", 999)
        out = StringIO()
        fd, ruta = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        self.addCleanup(os.remove, ruta)

        with patch(
            "apps.consulta_medica.management.commands.corregir_llave_familiares_legacy.Command.conectar_legado",
            return_value=self._legacy_conn(),
        ):
            call_command("corregir_llave_familiares_legacy", "--reporte", ruta, stdout=out)

        texto = out.getvalue()
        self.assertIn("LEGACY_TO_PK=1", texto)
        self.assertIn("UNKNOWN=1", texto)
        with open(ruta, encoding="utf-8") as fh:
            filas = list(csv.reader(fh))
        self.assertEqual(filas[0][0], "tipo")
        self.assertEqual([fila[0] for fila in filas[1:]], ["UNKNOWN"])
        self.assertTrue(Patient.objects.filter(no_exp="100", pk_num=501).exists())
