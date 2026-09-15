from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.catalogos.models import CatCies, Medicamentos
from apps.consulta_medica.models import PrescriptionAuthorization
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis
from apps.consulta_medica.uses_case.prescription_item_usecase import (
    add_prescription_item,
    authorize_prescription,
    cancel_prescription_item,
    list_pending_prescription_authorizations,
    list_prescription_authorizations_history,
    reject_prescription,
)
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

AUTHORIZE_PERMISSION = ["clinico:recetas:authorize"]


class PrescriptionAuthorizationUseCaseTests(TestCase):
    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_rx_test", correo="doctor_rx@example.com", clave_hash="x",
        ).id_usuario
        self.authorizer_id = SyUsuario.objects.create(
            usuario="authorizer_rx_test", correo="authorizer_rx@example.com", clave_hash="x",
        ).id_usuario

        CatCies.objects.create(
            code="I10", description="HIPERTENSION ESENCIAL", version="CIE-10", is_active=True,
        )

        self.med_basico = Medicamentos.objects.create(
            name="Paracetamol 500mg", cuadro_basico=Medicamentos.CuadroBasico.BASICO,
            is_controlled=False,
        )
        self.med_especial = Medicamentos.objects.create(
            name="Medicamento Especial X", cuadro_basico=Medicamentos.CuadroBasico.ESPECIAL,
            is_controlled=False,
        )
        self.med_controlado = Medicamentos.objects.create(
            name="Medicamento Controlado Y", cuadro_basico=Medicamentos.CuadroBasico.BASICO,
            is_controlled=True,
        )

    def _visit_in_consultation(self):
        visit = Visit.objects.create(
            folio=f"RXAUTH-{Visit.objects.count() + 1}",
            no_exp=f"EXP{9000 + Visit.objects.count() + 1}",
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-RXAUTH-{Visit.objects.count() + 1}",
            status="en_consulta",
        )
        save_diagnosis(
            visit_id=visit.id_visit, roles=["DOCTOR"],
            primary_diagnosis="Dx de prueba", final_note="Nota de prueba",
            doctor_id=self.doctor_id,
        )
        return visit

    def test_basico_medication_does_not_create_authorization(self):
        visit = self._visit_in_consultation()

        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_basico.id, quantity=10, indications="Cada 8 horas",
            actor_id=self.doctor_id,
        )

        self.assertEqual(PrescriptionAuthorization.objects.count(), 0)

    def test_especial_medication_creates_pending_authorization(self):
        visit = self._visit_in_consultation()

        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )

        auth = PrescriptionAuthorization.objects.get()
        self.assertEqual(auth.status, PrescriptionAuthorization.Status.PENDIENTE)
        self.assertEqual(auth.medications_count, 1)
        self.assertEqual(auth.specialized_count, 1)
        self.assertEqual(auth.controlled_count, 0)

    def test_controlled_medication_creates_pending_authorization(self):
        visit = self._visit_in_consultation()

        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_controlado.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )

        auth = PrescriptionAuthorization.objects.get()
        self.assertEqual(auth.controlled_count, 1)
        self.assertEqual(auth.specialized_count, 0)

    def test_second_special_item_does_not_duplicate_pending_authorization(self):
        visit = self._visit_in_consultation()

        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_controlado.id, quantity=1, indications="Cada 12 horas",
            actor_id=self.doctor_id,
        )

        self.assertEqual(PrescriptionAuthorization.objects.count(), 1)
        auth = PrescriptionAuthorization.objects.get()
        # La misma solicitud pendiente refleja el estado actualizado de
        # la receta completa, no solo el primer item que la disparo.
        self.assertEqual(auth.medications_count, 2)
        self.assertEqual(auth.specialized_count, 1)
        self.assertEqual(auth.controlled_count, 1)

    def test_authorize_pending_authorization(self):
        visit = self._visit_in_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        auth = PrescriptionAuthorization.objects.get()

        payload = authorize_prescription(
            auth.id_authorization, ["FARMACIA"],
            actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
        )

        self.assertEqual(payload["status"], "autorizada")
        self.assertEqual(payload["authorizedById"], self.authorizer_id)
        auth.refresh_from_db()
        self.assertEqual(auth.status, PrescriptionAuthorization.Status.AUTORIZADA)
        self.assertIsNotNone(auth.authorized_at)

    def test_reject_pending_authorization_requires_reason(self):
        visit = self._visit_in_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        auth = PrescriptionAuthorization.objects.get()

        with self.assertRaises(VisitDomainError) as raised:
            reject_prescription(
                auth.id_authorization, ["FARMACIA"], reason="   ",
                actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
            )
        self.assertEqual(raised.exception.code, "VALIDATION_ERROR")

        payload = reject_prescription(
            auth.id_authorization, ["FARMACIA"], reason="Sin existencias en farmacia",
            actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
        )
        self.assertEqual(payload["status"], "rechazada")
        self.assertEqual(payload["rejectionReason"], "Sin existencias en farmacia")

    def test_cannot_resolve_authorization_twice(self):
        visit = self._visit_in_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        auth = PrescriptionAuthorization.objects.get()
        authorize_prescription(
            auth.id_authorization, ["FARMACIA"],
            actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
        )

        with self.assertRaises(VisitDomainError) as raised:
            authorize_prescription(
                auth.id_authorization, ["FARMACIA"],
                actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
            )
        self.assertEqual(raised.exception.code, "AUTHORIZATION_ALREADY_RESOLVED")
        self.assertEqual(raised.exception.status_code, 409)

    def test_authorize_without_permission_raises(self):
        visit = self._visit_in_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        auth = PrescriptionAuthorization.objects.get()

        with self.assertRaises(VisitDomainError) as raised:
            authorize_prescription(
                auth.id_authorization, ["FARMACIA"],
                actor_id=self.authorizer_id, permissions=[],
            )
        self.assertEqual(raised.exception.code, "ROLE_NOT_ALLOWED")
        self.assertEqual(raised.exception.status_code, 403)

    def test_list_pending_only_returns_pending(self):
        visit_a = self._visit_in_consultation()
        add_prescription_item(
            visit_a.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        visit_b = self._visit_in_consultation()
        add_prescription_item(
            visit_b.id_visit, ["DOCTOR"],
            medication_id=self.med_controlado.id, quantity=1, indications="Cada 12 horas",
            actor_id=self.doctor_id,
        )
        auth_b = PrescriptionAuthorization.objects.get(prescription__id_visit=visit_b)
        authorize_prescription(
            auth_b.id_authorization, ["FARMACIA"],
            actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
        )

        result = list_pending_prescription_authorizations(
            ["FARMACIA"], permissions=AUTHORIZE_PERMISSION,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["visitId"], visit_a.id_visit)

    def test_cancel_item_does_not_retroactively_remove_pending_authorization(self):
        """
        Decision de diseño: cancelar el item que disparo la autorizacion
        NO la revierte automaticamente -- queda a criterio humano del
        autorizador (ver docstring del modelo).
        """
        visit = self._visit_in_consultation()
        item_payload = add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )

        cancel_prescription_item(
            visit.id_visit, item_payload["id"], ["DOCTOR"], actor_id=self.doctor_id,
        )

        auth = PrescriptionAuthorization.objects.get()
        self.assertEqual(auth.status, PrescriptionAuthorization.Status.PENDIENTE)

    def test_authorization_records_prescribed_by(self):
        visit = self._visit_in_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )

        auth = PrescriptionAuthorization.objects.get()
        self.assertEqual(auth.prescribed_by_id, self.doctor_id)

    def test_prescriber_cannot_authorize_own_prescription(self):
        """
        Segregacion de funciones: aunque el mismo medico tenga el permiso
        de autorizar (doble rol), no puede resolver una solicitud que el
        mismo genero al prescribir -- mismo problema que el legado
        intentaba resolver con det_clinicas.pw_autoriza.
        """
        visit = self._visit_in_consultation()
        add_prescription_item(
            visit.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        auth = PrescriptionAuthorization.objects.get()

        with self.assertRaises(VisitDomainError) as raised:
            authorize_prescription(
                auth.id_authorization, ["FARMACIA"],
                actor_id=self.doctor_id, permissions=AUTHORIZE_PERMISSION,
            )
        self.assertEqual(raised.exception.code, "SELF_AUTHORIZATION_NOT_ALLOWED")
        self.assertEqual(raised.exception.status_code, 403)

        with self.assertRaises(VisitDomainError) as raised:
            reject_prescription(
                auth.id_authorization, ["FARMACIA"], reason="No aplica",
                actor_id=self.doctor_id, permissions=AUTHORIZE_PERMISSION,
            )
        self.assertEqual(raised.exception.code, "SELF_AUTHORIZATION_NOT_ALLOWED")

        auth.refresh_from_db()
        self.assertEqual(auth.status, PrescriptionAuthorization.Status.PENDIENTE)

    def test_history_returns_all_statuses_and_filters_by_status(self):
        visit_a = self._visit_in_consultation()
        add_prescription_item(
            visit_a.id_visit, ["DOCTOR"],
            medication_id=self.med_especial.id, quantity=1, indications="Una vez al dia",
            actor_id=self.doctor_id,
        )
        visit_b = self._visit_in_consultation()
        add_prescription_item(
            visit_b.id_visit, ["DOCTOR"],
            medication_id=self.med_controlado.id, quantity=1, indications="Cada 12 horas",
            actor_id=self.doctor_id,
        )
        auth_a = PrescriptionAuthorization.objects.get(prescription__id_visit=visit_a)
        auth_b = PrescriptionAuthorization.objects.get(prescription__id_visit=visit_b)
        authorize_prescription(
            auth_a.id_authorization, ["FARMACIA"],
            actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
        )
        reject_prescription(
            auth_b.id_authorization, ["FARMACIA"], reason="Sin existencias",
            actor_id=self.authorizer_id, permissions=AUTHORIZE_PERMISSION,
        )

        full_history = list_prescription_authorizations_history(
            ["FARMACIA"], permissions=AUTHORIZE_PERMISSION,
        )
        self.assertEqual(full_history["total"], 2)

        only_rejected = list_prescription_authorizations_history(
            ["FARMACIA"], permissions=AUTHORIZE_PERMISSION, status="rechazada",
        )
        self.assertEqual(only_rejected["total"], 1)
        self.assertEqual(only_rejected["items"][0]["visitId"], visit_b.id_visit)

    def test_history_requires_authorize_permission(self):
        with self.assertRaises(VisitDomainError) as raised:
            list_prescription_authorizations_history(["FARMACIA"], permissions=[])
        self.assertEqual(raised.exception.code, "ROLE_NOT_ALLOWED")
