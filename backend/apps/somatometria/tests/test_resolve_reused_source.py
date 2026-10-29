"""
Tests unitarios de `_resolve_reused_source` (Fase 2, task 2.9 del change
somatometria-reuso-signos-mismo-dia). Valida los 4 codigos de error 422
que protegen la trazabilidad NOM-024 del reuso mismo dia.
"""
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.test import TestCase

from apps.recepcion.models import Visit
from apps.somatometria.repositories.vitals_repository import VitalsRepository
from apps.somatometria.services.visit_flow_service import VisitFlowError
from apps.somatometria.uses_case.capture_vitals_usecase import _resolve_reused_source
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


def _payload(**overrides):
    payload = {
        "weightKg": 70,
        "heightCm": 175,
        "temperatureC": 36.6,
        "oxygenSaturationPct": 98,
        "bmi": 22.86,
    }
    payload.update(overrides)
    return payload


def _create_visit(*, folio, no_exp, pk_num=0, status="en_somatometria"):
    return Visit.objects.create(
        folio=folio,
        patient=_paciente_de_llave(no_exp, pk_num),
        arrival_type=Visit.ArrivalType.WALK_IN,
        status=status,
    )


class ResolveReusedSourceTests(TestCase):
    def test_returns_none_when_no_reuse_requested(self):
        visit = _create_visit(folio="V-RS-NONE", no_exp="EXP-RS-1")

        self.assertIsNone(_resolve_reused_source(visit, None))

    def test_rejects_reusing_the_same_visit(self):
        visit = _create_visit(folio="V-RS-SAME", no_exp="EXP-RS-2")

        with self.assertRaises(VisitFlowError) as ctx:
            _resolve_reused_source(visit, visit.id_visit)

        self.assertEqual(ctx.exception.code, "REUSE_SAME_VISIT")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_rejects_nonexistent_source(self):
        visit = _create_visit(folio="V-RS-NOTFOUND", no_exp="EXP-RS-3")

        with self.assertRaises(VisitFlowError) as ctx:
            _resolve_reused_source(visit, 999999)

        self.assertEqual(ctx.exception.code, "REUSE_SOURCE_NOT_FOUND")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_rejects_source_from_another_patient(self):
        visit = _create_visit(folio="V-RS-MISMATCH-CUR", no_exp="EXP-RS-4")
        other_patient_visit = _create_visit(
            folio="V-RS-MISMATCH-SRC", no_exp="EXP-RS-OTHER", status="lista_para_doctor",
        )
        VitalsRepository.create_for_visit(other_patient_visit, _payload(), captured_by=None)

        with self.assertRaises(VisitFlowError) as ctx:
            _resolve_reused_source(visit, other_patient_visit.id_visit)

        self.assertEqual(ctx.exception.code, "REUSE_PATIENT_MISMATCH")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_rejects_source_from_another_family_member_same_no_exp(self):
        # Mismo no_exp (misma familia) pero distinto pk_num -> tambien es
        # "otra persona" para el reuso.
        visit = _create_visit(folio="V-RS-FAM-CUR", no_exp="EXP-RS-FAM", pk_num=0)
        other_member_visit = _create_visit(
            folio="V-RS-FAM-SRC", no_exp="EXP-RS-FAM", pk_num=2, status="lista_para_doctor",
        )
        VitalsRepository.create_for_visit(other_member_visit, _payload(), captured_by=None)

        with self.assertRaises(VisitFlowError) as ctx:
            _resolve_reused_source(visit, other_member_visit.id_visit)

        self.assertEqual(ctx.exception.code, "REUSE_PATIENT_MISMATCH")

    def test_rejects_source_captured_a_previous_local_day(self):
        visit = _create_visit(folio="V-RS-NOTTODAY-CUR", no_exp="EXP-RS-5")
        source_visit = _create_visit(
            folio="V-RS-NOTTODAY-SRC", no_exp="EXP-RS-5", status="lista_para_doctor",
        )

        yesterday_utc = datetime(2026, 8, 25, 18, 0, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=yesterday_utc):
            VitalsRepository.create_for_visit(source_visit, _payload(), captured_by=None)

        today_utc = datetime(2026, 8, 26, 18, 0, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=today_utc):
            with self.assertRaises(VisitFlowError) as ctx:
                _resolve_reused_source(visit, source_visit.id_visit)

        self.assertEqual(ctx.exception.code, "REUSE_NOT_TODAY")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_accepts_valid_source_same_patient_same_local_day(self):
        visit = _create_visit(folio="V-RS-OK-CUR", no_exp="EXP-RS-6")
        source_visit = _create_visit(
            folio="V-RS-OK-SRC", no_exp="EXP-RS-6", status="lista_para_doctor",
        )
        VitalsRepository.create_for_visit(source_visit, _payload(), captured_by=None)

        resolved = _resolve_reused_source(visit, source_visit.id_visit)

        self.assertEqual(resolved.id_visit, source_visit.id_visit)
