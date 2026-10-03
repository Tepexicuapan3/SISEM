"""
Identidad del paciente (documento "Historia Clinica Unificada", 5.1):
reglas de CURP, origen de la CURP, identificadores del familiar y uuid.
"""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.consulta_medica.models import ChangeLog, Patient
from apps.consulta_medica.services.curp_rules import (
    birth_date_from_curp,
    curp_mismatches,
    normalize_curp,
    sermed_sex_to_sires,
    sex_from_curp,
)
from apps.consulta_medica.uses_case.clinical_history_usecase import update_patient_profile
from apps.recepcion.services.errors import VisitDomainError

CURP_HOMBRE_1985 = "PEGJ850315HDFRRN09"
CURP_MUJER_1985 = "PEGJ850315MDFRRN01"
CURP_MUJER_2005 = "LOMA050720MDFPRNA3"


def _noop_audit_hook(**kwargs):
    return None


class CurpRulesTests(SimpleTestCase):
    def test_normalize_descarta_relleno_y_formato_invalido(self):
        self.assertIsNone(normalize_curp("SIN CURP"))
        self.assertIsNone(normalize_curp(""))
        self.assertIsNone(normalize_curp(None))
        self.assertIsNone(normalize_curp("PEGJ851315HDFRRN09"))  # mes 13
        self.assertEqual(normalize_curp(f"  {CURP_HOMBRE_1985.lower()} "), CURP_HOMBRE_1985)

    def test_fecha_de_nacimiento_usa_la_posicion_17_para_el_siglo(self):
        self.assertEqual(birth_date_from_curp(CURP_HOMBRE_1985), date(1985, 3, 15))
        self.assertEqual(birth_date_from_curp(CURP_MUJER_2005), date(2005, 7, 20))

    def test_sexo_de_la_curp(self):
        self.assertEqual(sex_from_curp(CURP_HOMBRE_1985), "H")
        self.assertEqual(sex_from_curp(CURP_MUJER_1985), "M")

    def test_sexo_de_sermed_se_traduce_al_de_sires(self):
        # En SERMED M = Masculino; en la CURP y en SIRES M = Mujer.
        self.assertEqual(sermed_sex_to_sires("M"), "H")
        self.assertEqual(sermed_sex_to_sires("F"), "M")
        self.assertEqual(sermed_sex_to_sires(" f "), "M")
        self.assertIsNone(sermed_sex_to_sires("X"))
        self.assertIsNone(sermed_sex_to_sires(None))

    def test_detecta_diferencias_con_los_datos_del_paciente(self):
        self.assertEqual(curp_mismatches(CURP_HOMBRE_1985, birth_date=date(1985, 3, 15), sex="H"), {})
        errores = curp_mismatches(CURP_HOMBRE_1985, birth_date=date(1990, 1, 1), sex="M")
        self.assertEqual(set(errores), {"birthDate", "sex"})
        # Lo que no se conoce no se compara.
        self.assertEqual(curp_mismatches(CURP_HOMBRE_1985), {})


class PatientIdentityModelTests(TestCase):
    def test_cada_paciente_recibe_un_uuid_distinto(self):
        a = Patient.objects.create(no_exp="100", pk_num=0)
        b = Patient.objects.create(no_exp="200", pk_num=0)

        self.assertIsNotNone(a.uuid)
        self.assertNotEqual(a.uuid, b.uuid)

    def test_familiar_del_legado_sin_pk_num_se_identifica_por_cd_familiar(self):
        Patient.objects.create(no_exp="300", pk_num=None, legacy_family_code=11)
        Patient.objects.create(no_exp="300", pk_num=None, legacy_family_code=12)

        self.assertEqual(Patient.objects.filter(no_exp="300", pk_num__isnull=True).count(), 2)

    def test_nadie_queda_sin_identificador(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Patient.objects.create(no_exp="400", pk_num=None, legacy_family_code=None)

    def test_cd_familiar_no_se_repite(self):
        Patient.objects.create(no_exp="500", pk_num=None, legacy_family_code=77)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Patient.objects.create(no_exp="501", pk_num=None, legacy_family_code=77)

    def test_no_exp_y_pk_num_no_se_repiten(self):
        Patient.objects.create(no_exp="600", pk_num=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Patient.objects.create(no_exp="600", pk_num=5)


class PatientCurpEditRulesTests(TestCase):
    def setUp(self):
        self.no_exp = "EXP5101"
        self.pk_num = 3

    def _update(self, data, actor_id=7):
        return update_patient_profile(
            self.no_exp, self.pk_num, ["DOCTOR"], data, actor_id=actor_id, audit_hook=_noop_audit_hook,
        )

    def _patient(self):
        return Patient.objects.get(no_exp=self.no_exp, pk_num=self.pk_num)

    def test_capturar_curp_la_marca_como_capturada_y_queda_en_la_bitacora(self):
        payload = self._update({"curp": CURP_HOMBRE_1985, "sex": "H"})

        self.assertEqual(payload["curpSource"], Patient.CurpSource.CAPTURED)
        entrada = ChangeLog.objects.get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.CAPTURE)
        self.assertEqual(entrada.table, "cns_paciente")
        self.assertEqual(entrada.user, "7")
        self.assertEqual(entrada.new_value["curp"], CURP_HOMBRE_1985)

    def test_sobrescribir_un_valor_es_correccion(self):
        self._update({"curp": CURP_HOMBRE_1985, "sex": "H"})
        self._update({"curp": CURP_MUJER_1985, "sex": "M"})

        ultima = ChangeLog.objects.order_by("-id_change").first()
        self.assertEqual(ultima.reason, ChangeLog.Reason.CORRECTION)
        self.assertEqual(ultima.previous_value["curp"], CURP_HOMBRE_1985)

    def test_borrar_la_curp_capturada_limpia_el_origen(self):
        self._update({"curp": CURP_HOMBRE_1985, "sex": "H"})
        payload = self._update({"curp": None})

        self.assertIsNone(payload["curp"])
        self.assertIsNone(payload["curpSource"])

    def test_la_curp_que_viene_de_sermed_no_se_edita(self):
        self._update({"sex": "H"})
        Patient.objects.filter(pk=self._patient().pk).update(
            curp=CURP_HOMBRE_1985, curp_source=Patient.CurpSource.SERMED,
        )

        with self.assertRaises(VisitDomainError) as ctx:
            self._update({"curp": CURP_MUJER_1985, "sex": "M"})

        self.assertEqual(ctx.exception.code, "CURP_FROM_SERMED")
        self.assertEqual(self._patient().curp, CURP_HOMBRE_1985)

    def test_mandar_la_misma_curp_de_sermed_no_es_una_edicion(self):
        self._update({"sex": "H"})
        Patient.objects.filter(pk=self._patient().pk).update(
            curp=CURP_HOMBRE_1985, curp_source=Patient.CurpSource.SERMED,
        )

        payload = self._update({"curp": CURP_HOMBRE_1985, "phone": "5555"})

        self.assertEqual(payload["curpSource"], Patient.CurpSource.SERMED)
        self.assertEqual(payload["phone"], "5555")

    def test_curp_de_otro_paciente_se_rechaza_e_indica_el_expediente(self):
        Patient.objects.create(no_exp="OTRO1", pk_num=0, curp=CURP_HOMBRE_1985)

        with self.assertRaises(VisitDomainError) as ctx:
            self._update({"curp": CURP_HOMBRE_1985, "sex": "H"})

        self.assertEqual(ctx.exception.code, "CURP_ALREADY_REGISTERED")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.details["noExp"], "OTRO1")
        self.assertIn("OTRO1", ctx.exception.message)

    def test_curp_que_no_coincide_con_el_sexo_se_rechaza(self):
        with self.assertRaises(VisitDomainError) as ctx:
            self._update({"curp": CURP_HOMBRE_1985, "sex": "M"})

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("sex", ctx.exception.details)
        self.assertFalse(ChangeLog.objects.exists())

    def test_cambiar_solo_el_sexo_tambien_se_valida_contra_la_curp(self):
        self._update({"curp": CURP_HOMBRE_1985, "sex": "H"})

        with self.assertRaises(VisitDomainError):
            self._update({"sex": "M"})

    def test_curp_que_no_coincide_con_la_fecha_de_nacimiento_se_rechaza(self):
        self._update({"sex": "H"})
        Patient.objects.filter(pk=self._patient().pk).update(birth_date=date(1990, 1, 1))

        with self.assertRaises(VisitDomainError) as ctx:
            self._update({"curp": CURP_HOMBRE_1985})

        self.assertIn("birthDate", ctx.exception.details)

    def test_el_contrato_expone_la_identidad_nueva(self):
        payload = self._update({"sex": "H"})

        for clave in ("uuid", "legacyFamilyCode", "paternalSurname", "maternalSurname",
                      "firstName", "birthDate", "curpSource"):
            self.assertIn(clave, payload)


class ReporteCurpDuplicadasTests(TestCase):
    def test_lista_las_curp_en_mas_de_un_paciente(self):
        Patient.objects.create(no_exp="A1", pk_num=0, curp=CURP_HOMBRE_1985)
        Patient.objects.create(no_exp="A2", pk_num=0, curp=CURP_HOMBRE_1985)
        Patient.objects.create(no_exp="A3", pk_num=0, curp=CURP_MUJER_1985)
        out = StringIO()

        call_command("reporte_curp_duplicadas", stdout=out)

        texto = out.getvalue()
        self.assertIn("CURP repetidas: 1", texto)
        self.assertIn("no_exp=A1", texto)
        self.assertIn("no_exp=A2", texto)
        self.assertNotIn("no_exp=A3", texto)

    def test_sin_repetidas_avisa_que_se_puede_agregar_la_restriccion(self):
        Patient.objects.create(no_exp="B1", pk_num=0, curp=CURP_HOMBRE_1985)
        out = StringIO()

        call_command("reporte_curp_duplicadas", stdout=out)

        self.assertIn("Sin CURP repetidas", out.getvalue())
