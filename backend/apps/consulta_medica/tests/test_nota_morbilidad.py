"""
5.3 paso 3: "primera vez / subsecuente de la enfermedad" (his_notas.sw_morbi)
y fecha de seguimiento (antes fe_cita), con las reglas del legado
(body-consultadirectac.jsp) adaptadas:
- sw_morbi es obligatorio para cerrar la nota (como en el legado).
- La fecha de seguimiento tiene que ser posterior a la consulta (mejora).
- SIRES sugiere el valor segun las consultas anteriores del paciente (mejora).
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies
from apps.consulta_medica.models import VisitConsultation, VisitConsultationRevision, VisitDiagnosis
from apps.consulta_medica.uses_case.consultation_usecase import (
    close_consultation,
    save_diagnosis,
    suggest_morbidity,
)
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


def _noop_audit_hook(**kwargs):
    return None


class _Base(TestCase):
    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_morbi", correo="morbi@example.com", clave_hash="x",
        ).id_usuario
        for code, name in (("I10", "HIPERTENSION ESENCIAL"), ("J00", "RINOFARINGITIS AGUDA")):
            CatCies.objects.create(code=code, description=name, version="CIE-10", is_active=True)
        self.today = timezone.localdate()

    def _visit(self, status="en_consulta", no_exp="EXP-MORBI", pk_num=0):
        n = Visit.objects.count() + 1
        return Visit.objects.create(
            folio=f"MRB-{n}", patient=_paciente_de_llave(no_exp, pk_num), arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-MRB-{n}", status=status, fecha_consulta=self.today,
        )

    def _close(self, visit, **extra):
        return close_consultation(
            visit_id=visit.id_visit, roles=["DOCTOR"], primary_diagnosis="Hipertension",
            final_note="Control", doctor_id=self.doctor_id, cie_code=extra.pop("cie_code", "I10"),
            audit_hook=_noop_audit_hook, **extra,
        )

    def _save(self, visit, **extra):
        return save_diagnosis(
            visit.id_visit, ["DOCTOR"], "Hipertension", "Control", self.doctor_id,
            cie_code="I10", audit_hook=_noop_audit_hook, **extra,
        )


class MorbidityRulesTests(_Base):
    def test_no_se_cierra_sin_primera_vez_o_subsecuente(self):
        visit = self._visit()

        with self.assertRaises(VisitDomainError) as raised:
            self._close(visit)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("morbidity", raised.exception.details)
        visit.refresh_from_db()
        self.assertEqual(visit.status, "en_consulta")

    def test_cerrar_guarda_morbilidad_y_seguimiento(self):
        visit = self._visit()
        follow_up = self.today + datetime.timedelta(days=30)

        payload = self._close(visit, morbidity="2", follow_up_date=follow_up)

        self.assertEqual(payload["consultation"]["morbidity"], "2")
        self.assertEqual(payload["consultation"]["followUpDate"], follow_up.isoformat())
        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.assertEqual((consultation.morbidity, consultation.follow_up_date), ("2", follow_up))

    def test_el_guardado_de_avance_no_exige_morbilidad(self):
        payload = self._save(self._visit())

        self.assertIsNone(payload["morbidity"])

    def test_seguimiento_el_mismo_dia_o_antes_se_rechaza(self):
        visit = self._visit()

        for day in (self.today, self.today - datetime.timedelta(days=1)):
            with self.assertRaises(VisitDomainError) as raised:
                self._save(visit, follow_up_date=day)
            self.assertIn("followUpDate", raised.exception.details)

    def test_cambiar_la_morbilidad_queda_versionado(self):
        visit = self._visit()
        self._save(visit, morbidity="1")

        self._save(visit, morbidity="2")

        revision = VisitConsultationRevision.objects.get()
        self.assertEqual(revision.previous_morbidity, "1")
        self.assertEqual(VisitConsultation.objects.get(id_visit=visit).morbidity, "2")

    def test_reintentar_el_mismo_cierre_es_idempotente(self):
        visit = self._visit()
        follow_up = self.today + datetime.timedelta(days=7)
        first = self._close(visit, morbidity="1", follow_up_date=follow_up)

        again = self._close(visit, morbidity="1", follow_up_date=follow_up)

        self.assertEqual(first["consultation"]["id"], again["consultation"]["id"])


class MorbiditySuggestionTests(_Base):
    def _closed_consultation(self, cie_code="I10", **visit_kwargs):
        visit = self._visit(**visit_kwargs)
        self._close(visit, morbidity="1", cie_code=cie_code)
        return visit

    def test_sin_consultas_previas_sugiere_primera_vez(self):
        suggestion = suggest_morbidity(self._visit().id_visit, ["DOCTOR"], "I10")

        self.assertEqual((suggestion["suggestion"], suggestion["previousConsultations"]), ("1", 0))

    def test_mismo_cie_en_otra_consulta_sugiere_subsecuente(self):
        self._closed_consultation("I10")

        suggestion = suggest_morbidity(self._visit().id_visit, ["DOCTOR"], "i10")

        self.assertEqual((suggestion["suggestion"], suggestion["previousConsultations"]), ("2", 1))

    def test_cuenta_tambien_el_diagnostico_secundario(self):
        previous = self._closed_consultation("J00")
        VisitDiagnosis.objects.create(
            consultation=VisitConsultation.objects.get(id_visit=previous), cie_id="I10",
        )

        self.assertEqual(suggest_morbidity(self._visit().id_visit, ["DOCTOR"], "I10")["suggestion"], "2")

    def test_otro_cie_u_otro_paciente_no_cuentan(self):
        self._closed_consultation("J00")
        self._closed_consultation("I10", no_exp="OTRO-EXP")

        self.assertEqual(suggest_morbidity(self._visit().id_visit, ["DOCTOR"], "I10")["suggestion"], "1")

    def test_sin_cie_no_sugiere(self):
        self.assertIsNone(suggest_morbidity(self._visit().id_visit, ["DOCTOR"], "")["suggestion"])
