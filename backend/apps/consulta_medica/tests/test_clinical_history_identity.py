"""
Identidad del paciente en PACIENTE (`Patient`): CURP y sexo
(H/M/X), versionados como el resto de la historia; y limpieza del texto
libre de alergias (deprecado a favor de `Allergy`).
"""
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.consulta_medica.models import Allergy, HistoricalNote, Patient, PatientRevision
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase
from apps.consulta_medica.tests.test_migrar_historial_clinico_legacy import (
    _LEGACY_ROW_BASE,
    _mock_conn,
)

VALID_CURP = "PEGJ850315HDFRRN09"


class ClinicalHistoryIdentityApiTests(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.no_exp = "EXPID1"
        self.url = f"/api/v1/patients/{self.no_exp}/profile?pkNum=0"
        self._login_doctor()

    def _patch(self, body):
        return self.client.patch(
            self.url, body, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def test_saves_and_returns_curp_and_sex(self):
        response = self._patch({"curp": VALID_CURP, "sex": "H"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["curp"], VALID_CURP)
        self.assertEqual(response.data["sex"], "H")
        read = self.client.get(self.url)
        self.assertEqual(read.data["curp"], VALID_CURP)
        self.assertEqual(read.data["sex"], "H")

    def test_normalizes_curp_to_uppercase_and_blank_to_null(self):
        # VALID_CURP es de hombre: el sexo tiene que coincidir con su letra 11 (5.1).
        normalized = self._patch({"curp": f"  {VALID_CURP.lower()} ", "sex": "H"})
        cleared = self._patch({"curp": "", "sex": ""})

        self.assertEqual(normalized.data["curp"], VALID_CURP)
        self.assertEqual(normalized.data["sex"], "H")
        self.assertIsNone(cleared.data["curp"])
        self.assertIsNone(cleared.data["sex"])

    def test_rejects_invalid_curp_and_sex(self):
        response = self._patch({"curp": "PEGJ851315HDFRRN09", "sex": "Z"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(set(response.data["details"]), {"curp", "sex"})
        self.assertFalse(Patient.objects.filter(no_exp=self.no_exp).exclude(curp=None).exists())

    def test_overwriting_curp_is_versioned_and_audited(self):
        self._patch({"curp": VALID_CURP, "sex": "H"})

        self._patch({"curp": "PEGJ850315MDFRRN01", "sex": "M"})

        revision = PatientRevision.objects.get()
        self.assertEqual(revision.previous_curp, VALID_CURP)
        self.assertEqual(revision.previous_sex, "H")
        event = AuditoriaEvento.objects.filter(accion="PatientProfileUpdated").latest("id_evento")
        self.assertEqual(event.datos_antes["curp"], VALID_CURP)
        self.assertEqual(sorted(event.datos_despues["changedFields"]), ["curp", "sex"])

    def test_accepts_legacy_phone_format_longer_than_15(self):
        legacy_phone = "cel 55-1234-5678 tel 5555-5555 ext 12345"

        response = self._patch({"phone": legacy_phone})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone"], legacy_phone)

    def test_allergies_free_text_is_no_longer_exposed_nor_writable(self):
        response = self._patch({"allergies": "Penicilina", "sex": "M"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("allergies", response.data)


class LegacyCommandAllergyImportTests(_ConsultationAuditApiTestBase):
    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_legacy_allergies_go_to_structured_table_idempotently(self, mock_connect):
        # Texto acumulado real del legado: una anotacion firmada por captura.
        row = dict(
            _LEGACY_ROW_BASE,
            ds_alergias="Penicilina, sulfas [01/02/2020 (jperez)] - NEGADAS [03/04/2021 (mlopez)] - ",
        )
        mock_connect.return_value = _mock_conn([row])
        out = StringIO()

        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x", database="x", stdout=out)
        mock_connect.return_value = _mock_conn([row])
        call_command("migrar_historial_clinico_legacy", host="x", user="x", password="x", database="x")

        substances = sorted(Allergy.objects.filter(no_exp="EXP-0001").values_list("substance", flat=True))
        # Una fila por elemento, tipo "otro" (documento); "NEGADAS" no es alergia.
        self.assertEqual(substances, ["Penicilina", "sulfas"])
        self.assertEqual(
            set(Allergy.objects.values_list("allergy_type_id", flat=True)), {9},
        )
        notes = HistoricalNote.objects.filter(no_exp="EXP-0001", section="alergias").order_by("noted_on")
        self.assertEqual(
            [(n.content, n.author, str(n.noted_on)) for n in notes],
            [("Penicilina, sulfas", "jperez", "2020-02-01"), ("NEGADAS", "mlopez", "2021-04-03")],
        )
        self.assertIn("Alergias importadas a cns_allergy: 2", out.getvalue())

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_dry_run_counts_allergies_without_writing(self, mock_connect):
        mock_connect.return_value = _mock_conn([dict(_LEGACY_ROW_BASE, ds_alergias="Sulfas")])
        out = StringIO()

        call_command(
            "migrar_historial_clinico_legacy", host="x", user="x", password="x", database="x",
            dry_run=True, stdout=out,
        )

        self.assertFalse(Allergy.objects.exists())
        self.assertFalse(HistoricalNote.objects.exists())
        self.assertIn("[dry-run]", out.getvalue())
