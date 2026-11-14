"""Crónicos, entrega 3: alta al padrón con identidad y origen del diagnóstico
(docs/plans/cronicos-alta-padron.md)."""
from datetime import date, timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCies
from apps.catalogos.tests.designacion_factories import make_center
from apps.catalogos.tests.test_designacion_api import _login_client
from apps.consulta_medica.models import Patient
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.padrones.uses_case import aviso_consulta_usecase as aviso
from apps.padrones.uses_case import padron_usecase as uc
from apps.recepcion.contracts import patient_lookup_contract
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

WRITE = ["clinico:padrones:read", "clinico:padrones:write"]
DOCTOR_ENROLLS = ["clinico:consultas:read", "clinico:padrones:write"]
TODAY = timezone.localdate()
LOOKUP = "apps.recepcion.uses_case.visit_queue_usecase.lookup_patient"  # el contrato la importa al llamar
FAMILY = "apps.padrones.uses_case.padron_usecase.family_members"

SERMED_FAMILY = {
    "titular": {
        "noExp": "777", "pkNum": 0, "nombre": "PEREZ LOPEZ JUAN", "edad": 52, "fechaNac": "1974-03-01",
        "parentesco": "TRABAJADOR", "estatus": "ACTIVO", "cdClinica": "01", "idPaciente": 10,
        "foto": "data:image/jpeg;base64,AAAA", "adscripcion": {"estado": "ok"},
    },
    "dependientes": [{
        "noExp": "777", "pkNum": 2, "nombre": "RUIZ SOTO MARIA", "edad": 49, "fechaNac": "1977-06-10",
        "parentesco": "ESPOSA", "estatus": "ACTIVO", "cdClinica": "01", "idPaciente": None,
        "foto": None, "adscripcion": None,
    }],
}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = SyUsuario.objects.create(usuario="alta_padron", clave_hash="x")
        cls.center = make_center()
        for code, description in [("E11", "DIABETES TIPO 2"), ("J00", "RINOFARINGITIS AGUDA")]:
            CatCies.objects.get_or_create(code=code, defaults={"description": description, "version": "CIE-10"})

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _enroll(self, **kw):
        data = dict(no_exp="EXP-ALTA", pk_num=0, item_id="E11", center_id=self.center.pk,
                    actor=self.actor, permissions=WRITE)
        data.update(kw)
        return uc.enroll("cronicos", **data)


class FamilyContractTests(TestCase):
    def test_members_without_photo_nor_adscription(self):
        with mock.patch(LOOKUP, return_value=SERMED_FAMILY) as lookup:
            members = patient_lookup_contract.family_members(" 777 ")
        lookup.assert_called_once_with("777", historico=False, incluir_fotos=False)
        self.assertEqual([m["pkNum"] for m in members], [0, 2])
        self.assertEqual(members[1], {
            "idPaciente": None, "noExp": "777", "pkNum": 2, "nombre": "RUIZ SOTO MARIA",
            "parentesco": "ESPOSA", "edad": 49, "fechaNac": "1977-06-10",
        })
        self.assertNotIn("foto", members[0])

    def test_inactive_titular_is_skipped(self):
        family = {"titular": None, "dependientes": SERMED_FAMILY["dependientes"]}
        with mock.patch(LOOKUP, return_value=family):
            self.assertEqual([m["pkNum"] for m in patient_lookup_contract.family_members("777")], [2])


class FamilyForEnrollmentTests(_Base):
    def test_requires_padron_write(self):
        with self.assertRaises(VisitDomainError) as ctx:
            uc.family_for_enrollment("777", permissions=["clinico:padrones:read"])
        self.assertEqual(ctx.exception.status_code, 403)

    def test_requires_expediente(self):
        with self.assertRaises(VisitDomainError) as ctx:
            uc.family_for_enrollment("  ", permissions=WRITE)
        self.assertIn("noExp", ctx.exception.details)

    def test_returns_members_from_contract(self):
        with mock.patch(FAMILY, return_value=[{"pkNum": 0}]) as family:
            self.assertEqual(uc.family_for_enrollment(" 777 ", permissions=WRITE), {"members": [{"pkNum": 0}]})
        family.assert_called_once_with("777")


class SourceTests(_Base):
    def test_manual_enrollment_is_marked_manual(self):
        enrollment = self._enroll()
        self.assertEqual((enrollment.source, enrollment.visit_id), ("manual", None))
        contract = uc.to_contract(uc.get_kind("cronicos"), enrollment, permissions=WRITE, roles=[])
        self.assertEqual(contract["source"], "manual")

    def test_enrollment_from_visit_keeps_the_visit(self):
        visit = Visit.objects.create(
            folio="V-ALTA-1", patient=paciente_de_llave("EXP-ALTA-V", 0), arrival_type="walk_in",
            service_type="medicina_general", status="en_consulta", nombre_paciente="Paciente Alta",
            centro=self.center,
        )
        enrollment = aviso.enroll_from_visit(visit.id_visit, item_id="E11", actor=self.actor,
                                             permissions=DOCTOR_ENROLLS)
        self.assertEqual((enrollment.source, enrollment.visit_id), ("consulta", visit.id_visit))


class OptionsProgramTests(_Base):
    def test_each_cie_option_says_its_program(self):
        items = {i["code"]: i for i in uc.search_options("cronicos", search="E11", permissions=WRITE)["items"]}
        self.assertEqual(items["E11"]["program"]["code"], "DIABETES")
        acute = uc.search_options("cronicos", search="J00", permissions=WRITE)["items"][0]
        self.assertIsNone(acute["program"])


class EnrolledOnBirthDateTests(_Base):
    def test_cannot_enroll_before_birth(self):
        patient = paciente_de_llave("EXP-ALTA", 0)
        Patient.objects.filter(pk=patient.pk).update(birth_date=date(2000, 1, 1))
        with self.assertRaises(VisitDomainError) as ctx:
            self._enroll(enrolled_on=date(1999, 12, 31))
        self.assertIn("enrolledOn", ctx.exception.details)
        self.assertEqual(self._enroll(enrolled_on=date(2000, 1, 1)).enrolled_on, date(2000, 1, 1))

    def test_unknown_birth_date_does_not_block(self):
        self.assertEqual(self._enroll(enrolled_on=TODAY - timedelta(days=4000)).status, "activo")


class MembersApiTests(_Base):
    def setUp(self):
        super().setUp()
        self.client_api, self.user = _login_client("trabajo_social_alta", WRITE)
        DetUsuario.objects.filter(id_usuario=self.user).update(id_centro_atencion=self.center)

    def test_members_endpoint(self):
        with mock.patch(FAMILY, return_value=[{"pkNum": 0, "nombre": "PEREZ"}]):
            response = self.client_api.get("/api/v1/padrones/miembros?noExp=777")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["members"][0]["nombre"], "PEREZ")

    def test_members_endpoint_errors(self):
        self.assertEqual(self.client_api.get("/api/v1/padrones/miembros").status_code, 422)
        reader, _ = _login_client("solo_lectura_alta", ["clinico:padrones:read"])
        self.assertEqual(reader.get("/api/v1/padrones/miembros?noExp=777").status_code, 403)
        missing = VisitDomainError("PATIENT_NOT_FOUND", "Expediente no encontrado.", 404)
        with mock.patch(FAMILY, side_effect=missing):
            response = self.client_api.get("/api/v1/padrones/miembros?noExp=000")
        self.assertEqual((response.status_code, response.data["code"]), (404, "PATIENT_NOT_FOUND"))
