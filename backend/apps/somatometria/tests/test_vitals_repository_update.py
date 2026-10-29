"""
Tests unitarios de `VitalsRepository.create_for_visit` / `update_for_visit`
(Fase 2, tasks 2.7 y 2.10 del change somatometria-modulo-integral).

Cubre:
- Captura inicial guarda SOLO `captured_by` (`updated_by` queda `null`).
- Una correccion (`update_for_visit`) NUNCA toca `captured_by` ni
  `reused_from_visit`, y SI actualiza `updated_by`.
- Gotcha D2: `update_for_visit` debe re-sincronizar `PatientLatestVitals`
  -- si no lo hiciera, la proxima consulta precargaria el valor viejo
  (no corregido).
"""
from django.contrib.auth.hashers import make_password
from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.recepcion.models import Visit
from apps.somatometria.models import PatientLatestVitals
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


def _create_visit(*, folio, no_exp, pk_num=0, status="en_somatometria"):
    return Visit.objects.create(
        folio=folio,
        patient=_paciente_de_llave(no_exp, pk_num),
        arrival_type=Visit.ArrivalType.WALK_IN,
        status=status,
    )


def _create_user(username):
    return SyUsuario.objects.create(
        usuario=username,
        correo=f"{username}@example.com",
        clave_hash=make_password("Somato_123456"),
        est_activo=True,
        cambiar_clave=False,
        terminos_acept=True,
    )


class CreateForVisitAttributionTests(TestCase):
    def test_create_records_only_captured_by(self):
        visit = _create_visit(folio="V-ATTR-CREATE", no_exp="EXP-ATTR-1")
        nurse_a = _create_user("nurse_a_create")

        vital_signs = VitalsRepository.create_for_visit(
            visit, _payload(), captured_by=nurse_a,
        )

        self.assertEqual(vital_signs.captured_by_id, nurse_a.id_usuario)
        self.assertIsNone(vital_signs.updated_by_id)

    def test_captured_by_is_kwarg_only_and_required(self):
        visit = _create_visit(folio="V-ATTR-KWARG", no_exp="EXP-ATTR-KW")

        with self.assertRaises(TypeError):
            VitalsRepository.create_for_visit(visit, _payload())  # falta captured_by


class UpdateForVisitAttributionTests(TestCase):
    def test_correction_does_not_erase_original_captured_by(self):
        visit = _create_visit(folio="V-ATTR-UPDATE", no_exp="EXP-ATTR-2")
        nurse_a = _create_user("nurse_a_update")
        nurse_b = _create_user("nurse_b_update")

        vital_signs = VitalsRepository.create_for_visit(
            visit, _payload(), captured_by=nurse_a,
        )

        corrected = VitalsRepository.update_for_visit(
            vital_signs,
            _payload(weightKg=72, bmi=23.51),
            updated_by=nurse_b,
        )

        self.assertEqual(corrected.captured_by_id, nurse_a.id_usuario)
        self.assertEqual(corrected.updated_by_id, nurse_b.id_usuario)
        self.assertEqual(float(corrected.weight_kg), 72.0)

    def test_update_does_not_touch_reused_from_visit(self):
        source = _create_visit(folio="V-ATTR-SRC", no_exp="EXP-ATTR-3")
        current = _create_visit(folio="V-ATTR-CUR", no_exp="EXP-ATTR-3")
        nurse_a = _create_user("nurse_a_reuse")
        nurse_b = _create_user("nurse_b_reuse")

        vital_signs = VitalsRepository.create_for_visit(
            current, _payload(), reused_from=source, captured_by=nurse_a,
        )

        corrected = VitalsRepository.update_for_visit(
            vital_signs, _payload(weightKg=72, bmi=23.51), updated_by=nurse_b,
        )

        self.assertEqual(corrected.reused_from_visit_id, source.id_visit)

    def test_update_resyncs_patient_latest_vitals_gotcha_d2(self):
        """
        Gotcha D2: si `update_for_visit` no re-espeja `PatientLatestVitals`,
        la proxima consulta (que precarga el formulario) devuelve el valor
        VIEJO -- no el corregido.
        """
        visit = _create_visit(folio="V-ATTR-LATEST", no_exp="EXP-ATTR-4")
        nurse_a = _create_user("nurse_a_latest")
        nurse_b = _create_user("nurse_b_latest")

        vital_signs = VitalsRepository.create_for_visit(
            visit, _payload(weightKg=70), captured_by=nurse_a,
        )

        latest_before = PatientLatestVitals.objects.get(patient__no_exp="EXP-ATTR-4", patient__pk_num=0)
        self.assertEqual(float(latest_before.weight_kg), 70.0)

        VitalsRepository.update_for_visit(
            vital_signs, _payload(weightKg=68, bmi=22.2), updated_by=nurse_b,
        )

        latest_after = PatientLatestVitals.objects.get(patient__no_exp="EXP-ATTR-4", patient__pk_num=0)
        self.assertEqual(
            float(latest_after.weight_kg),
            68.0,
            "update_for_visit debe re-sincronizar PatientLatestVitals con "
            "el valor CORREGIDO, sino la proxima consulta precarga el "
            "valor viejo (gotcha D2).",
        )
