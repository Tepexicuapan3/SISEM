"""
Tests unitarios de `VitalsRepository.get_latest_today_for_patient`
(Fase 2, task 2.7 + 2.8 del change somatometria-reuso-signos-mismo-dia).

Valida spec "Captura existente el mismo día local", "La visita actual se
excluye" y el borde de zona horaria 23:55 -> 00:10 (el corte de "hoy" es
SIEMPRE el dia calendario LOCAL -- America/Mexico_City -- nunca UTC crudo).

No usamos `freezegun` (no esta instalado en el proyecto): el equivalente
estandar de Django es parchear `django.utils.timezone.now`, que es la
funcion que tanto `auto_now_add` (para fijar `fch_alta`) como
`timezone.localdate()`/`timezone.localtime()` (usados por el repositorio)
consultan internamente.
"""
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.test import TestCase

from apps.recepcion.models import Visit
from apps.somatometria.repositories.vitals_repository import VitalsRepository
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


def _pid(no_exp, pk_num):
    """Registro del paciente (plan contraer la llave vieja: se busca por id_paciente)."""
    from apps.consulta_medica.models import Patient

    return Patient.objects.get(no_exp=no_exp, pk_num=pk_num).pk


def _create_visit(*, folio, no_exp, pk_num=0, status="lista_para_doctor"):
    return Visit.objects.create(
        folio=folio,
        patient=_paciente_de_llave(no_exp, pk_num),
        arrival_type=Visit.ArrivalType.WALK_IN,
        status=status,
    )


class GetLatestTodayForPatientTests(TestCase):
    """Task 2.7 -- exclusiones de `get_latest_today_for_patient`."""

    def test_finds_capture_from_today_same_person_different_visit(self):
        source = _create_visit(folio="V-TODAY-SRC", no_exp="EXP-TODAY-1")
        current = _create_visit(
            folio="V-TODAY-CUR", no_exp="EXP-TODAY-1", status="en_somatometria",
        )
        VitalsRepository.create_for_visit(source, _payload(), captured_by=None)

        found = VitalsRepository.get_latest_today_for_patient(
            _pid("EXP-TODAY-1", 0), exclude_visit_id=current.id_visit,
        )

        self.assertIsNotNone(found)
        self.assertEqual(found.id_visit_id, source.id_visit)

    def test_excludes_current_visit(self):
        current = _create_visit(
            folio="V-SELF-1", no_exp="EXP-SELF-1", status="en_somatometria",
        )
        VitalsRepository.create_for_visit(current, _payload(), captured_by=None)

        found = VitalsRepository.get_latest_today_for_patient(
            _pid("EXP-SELF-1", 0), exclude_visit_id=current.id_visit,
        )

        self.assertIsNone(found, "la propia visita nunca debe ofrecerse como reuso de si misma")

    def test_excludes_other_family_member_same_no_exp(self):
        titular = _create_visit(folio="V-FAM-0", no_exp="EXP-FAM-1", pk_num=0)
        derechohabiente = _create_visit(
            folio="V-FAM-2", no_exp="EXP-FAM-1", pk_num=2, status="en_somatometria",
        )
        VitalsRepository.create_for_visit(titular, _payload(), captured_by=None)

        found = VitalsRepository.get_latest_today_for_patient(
            _pid("EXP-FAM-1", 2), exclude_visit_id=derechohabiente.id_visit,
        )

        self.assertIsNone(found, "no debe mezclar el reuso entre integrantes del mismo no_exp")

    def test_excludes_cancelled_and_no_show_source_visits(self):
        for status_value in ("cancelada", "no_show"):
            with self.subTest(status=status_value):
                source = _create_visit(
                    folio=f"V-{status_value}-SRC",
                    no_exp=f"EXP-{status_value}",
                    status=status_value,
                )
                current = _create_visit(
                    folio=f"V-{status_value}-CUR",
                    no_exp=f"EXP-{status_value}",
                    status="en_somatometria",
                )
                VitalsRepository.create_for_visit(source, _payload(), captured_by=None)

                found = VitalsRepository.get_latest_today_for_patient(
                    _pid(f"EXP-{status_value}", 0), exclude_visit_id=current.id_visit,
                )

                self.assertIsNone(found)

    def test_excludes_capture_from_a_previous_local_day(self):
        source = _create_visit(folio="V-YEST-SRC", no_exp="EXP-YEST-1")
        current = _create_visit(
            folio="V-YEST-CUR", no_exp="EXP-YEST-1", status="en_somatometria",
        )

        yesterday_utc = datetime(2026, 8, 25, 18, 0, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=yesterday_utc):
            VitalsRepository.create_for_visit(source, _payload(), captured_by=None)

        today_utc = datetime(2026, 8, 26, 18, 0, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=today_utc):
            found = VitalsRepository.get_latest_today_for_patient(
                _pid("EXP-YEST-1", 0), exclude_visit_id=current.id_visit,
            )

        self.assertIsNone(found)

    def test_returns_none_when_no_exp_is_missing(self):
        # Visita sin registro de paciente: nunca hay reuso posible.
        found = VitalsRepository.get_latest_today_for_patient(
            None, exclude_visit_id=999999,
        )
        self.assertIsNone(found)


class GetLatestTodayForPatientTimezoneBoundaryTests(TestCase):
    """
    Task 2.8 -- borde de zona horaria 23:55 -> 00:10 (spec "Borde de zona
    horaria 23:55 -> 00:10"). America/Mexico_City es UTC-6 sin horario de
    verano desde 2022, asi que el offset es fijo.
    """

    def test_capture_23_50_local_not_offered_at_00_10_next_local_day(self):
        source = _create_visit(folio="V-TZ-SRC", no_exp="EXP-TZ-1")
        current = _create_visit(
            folio="V-TZ-CUR", no_exp="EXP-TZ-1", status="en_somatometria",
        )

        # 2026-08-26T05:50:00Z == 2026-08-25 23:50 hora CDMX (UTC-6).
        capture_instant_utc = datetime(2026, 8, 26, 5, 50, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=capture_instant_utc):
            VitalsRepository.create_for_visit(source, _payload(), captured_by=None)

        # 2026-08-26T06:10:00Z == 2026-08-26 00:10 hora CDMX: solo 20 min
        # de reloj despues, pero cruza la medianoche LOCAL.
        query_instant_utc = datetime(2026, 8, 26, 6, 10, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=query_instant_utc):
            found = VitalsRepository.get_latest_today_for_patient(
                _pid("EXP-TZ-1", 0), exclude_visit_id=current.id_visit,
            )

        self.assertIsNone(
            found,
            "una captura de las 23:50 del dia local anterior no debe "
            "ofrecerse a las 00:10 del dia siguiente (el corte es por dia "
            "calendario LOCAL, no por UTC crudo)",
        )

    def test_capture_23_50_local_still_offered_within_the_same_local_day(self):
        # Control del test anterior: la MISMA captura si se ofrece si la
        # consulta cae en el mismo dia calendario local (23:55, 5 min
        # despues, dentro del mismo dia D).
        source = _create_visit(folio="V-TZ-SRC-2", no_exp="EXP-TZ-2")
        current = _create_visit(
            folio="V-TZ-CUR-2", no_exp="EXP-TZ-2", status="en_somatometria",
        )

        capture_instant_utc = datetime(2026, 8, 26, 5, 50, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=capture_instant_utc):
            VitalsRepository.create_for_visit(source, _payload(), captured_by=None)

        same_local_day_query_utc = datetime(2026, 8, 26, 5, 55, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=same_local_day_query_utc):
            found = VitalsRepository.get_latest_today_for_patient(
                _pid("EXP-TZ-2", 0), exclude_visit_id=current.id_visit,
            )

        self.assertIsNotNone(found)
        self.assertEqual(found.id_visit_id, source.id_visit)
