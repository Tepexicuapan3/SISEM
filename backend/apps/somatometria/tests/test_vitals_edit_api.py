"""
Test de integracion (APIClient) de la edicion auditada de signos vitales
(Fase 3 + Fase 4a del change somatometria-modulo-integral).

Cubre:
- 3.8: PATCH sin `motivo` -> 400, fila sin cambios.
- 3.9: edicion exitosa -> exactamente 1 `AuditoriaEvento` "VitalsEdited",
  `datos_antes != datos_despues`, `motivo` en `meta`.
- 3.10: si la escritura de auditoria falla, TODA la transaccion revierte
  -- la fila queda con sus valores ORIGINALES, sin `AuditoriaEvento`
  parcial.
- 3.11: una correccion NO borra `captured_by` (A captura, B corrige ->
  `captured_by` sigue siendo A, `updated_by = B`).
- 4a.5: usuario con `flow.somatometria.capture` pero SIN
  `flow.somatometria.edit` -> 403 en PATCH.
- 4a.6: usuario con capabilities de `flow.doctor.*` -> 403 en POST y PATCH.
"""
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles
from apps.recepcion.models import Visit
from apps.somatometria.models import VisitVitalSigns
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


class VitalsEditApiTestsBase(APITestCase):
    def setUp(self):
        self.request_id = "55555555-5555-5555-5555-555555555555"
        self.password = "Somato_123456"

        self.editor = self._create_user_with_role(
            username="somato_editor",
            email="somato_editor@example.com",
            role_code="SOMATOMETRIA_EDITOR",
            permissions=["clinico:somatometria:read", "clinico:somatometria:update"],
        )
        self.captor = self._create_user_with_role(
            username="somato_captor",
            email="somato_captor@example.com",
            role_code="SOMATOMETRIA_CAPTOR",
            permissions=["clinico:somatometria:read"],
        )
        self.doctor = self._create_user_with_role(
            username="somato_doctor",
            email="somato_doctor@example.com",
            role_code="SOMATOMETRIA_DOCTOR",
            permissions=["clinico:consultas:read"],
        )

        self.visit = Visit.objects.create(
            folio="EDIT-0001",
            patient=_paciente_de_llave("EXP-EDIT-API-1", 0),
            arrival_type=Visit.ArrivalType.WALK_IN,
            status="en_somatometria",
            service_type=Visit.ServiceType.MEDICINA_GENERAL,
        )

    def _create_user_with_role(self, *, username, email, role_code, permissions=None):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=email,
            clave_hash=make_password(self.password),
            est_activo=True,
            cambiar_clave=False,
            terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user,
            nombre=username,
            paterno="Test",
            materno="User",
        )
        role, _ = Roles.objects.get_or_create(
            rol=role_code,
            defaults={
                "desc_rol": f"Rol {role_code}",
                "landing_route": "/clinico/somatometria",
            },
        )
        for permission_code in permissions or []:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code,
                defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        return user

    def _login_as(self, username):
        self.client.cookies.clear()
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": username, "password": self.password},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def _csrf_headers(self):
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _valid_capture_payload(self, **overrides):
        payload = {
            "weightKg": 70,
            "heightCm": 175,
            "temperatureC": 36.6,
            "oxygenSaturationPct": 98,
        }
        payload.update(overrides)
        return payload

    def _valid_edit_payload(self, **overrides):
        payload = {
            "weightKg": 72,
            "heightCm": 175,
            "temperatureC": 36.8,
            "oxygenSaturationPct": 97,
            "motivo": "Bascula mal calibrada en la primera toma",
        }
        payload.update(overrides)
        return payload

    def _capture_as(self, user, **overrides):
        self._login_as(user.usuario)
        response = self.client.post(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_capture_payload(**overrides),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response


class VitalsEditValidationTests(VitalsEditApiTestsBase):
    def test_patch_without_motivo_returns_400_and_row_untouched(self):
        self._capture_as(self.captor)

        self._login_as(self.editor.usuario)
        payload = self._valid_edit_payload()
        payload.pop("motivo")

        response = self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            payload,
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertEqual(float(row.weight_kg), 70.0)
        self.assertIsNone(row.updated_by_id)

    def test_patch_with_short_motivo_returns_400_and_row_untouched(self):
        self._capture_as(self.captor)

        self._login_as(self.editor.usuario)
        response = self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_edit_payload(motivo="abc"),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertIsNone(row.updated_by_id)


class VitalsEditAuditTests(VitalsEditApiTestsBase):
    def test_successful_edit_creates_exactly_one_audit_event_with_diff_and_motivo(self):
        self._capture_as(self.captor)

        self._login_as(self.editor.usuario)
        motivo = "Correccion por bascula mal calibrada"
        response = self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_edit_payload(weightKg=72, motivo=motivo),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        events = AuditoriaEvento.objects.filter(accion="VitalsEdited")
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.recurso_tipo, "vitals")
        self.assertNotEqual(event.datos_antes, event.datos_despues)
        self.assertEqual(event.datos_antes["weightKg"], 70.0)
        self.assertEqual(event.datos_despues["weightKg"], 72.0)
        self.assertEqual(event.meta.get("motivo"), motivo)

        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertEqual(float(row.weight_kg), 72.0)

    def test_edit_does_not_change_visit_status_or_reused_from(self):
        self._capture_as(self.captor)
        self.visit.refresh_from_db()
        status_after_capture = self.visit.status

        self._login_as(self.editor.usuario)
        response = self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_edit_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # D8: la respuesta del PATCH no trae "status" -- a diferencia del
        # POST, la edicion no avanza el flujo de la visita.
        self.assertNotIn("status", response.data)
        self.visit.refresh_from_db()
        self.assertEqual(
            self.visit.status,
            status_after_capture,
            "El PATCH de edicion NO debe alterar el status de la visita "
            "(D8): debe quedar exactamente igual al que dejo la captura.",
        )

    def test_audit_failure_rolls_back_entire_edit(self):
        """
        3.10: si `AuditoriaEvento.objects.create` falla dentro del
        `audit_hook`, `raise_on_error=True` propaga la excepcion y
        `transaction.atomic()` revierte TAMBIEN el `update_for_visit` que
        ya habia corrido -- la fila debe quedar con los valores
        ORIGINALES, sin ningun `AuditoriaEvento` parcial.
        """
        self._capture_as(self.captor)
        self._login_as(self.editor.usuario)

        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create"
        ) as create_mock:
            create_mock.side_effect = RuntimeError("db down")
            # El proyecto tiene un EXCEPTION_HANDLER global
            # (`custom_exception_handler`) que convierte CUALQUIER
            # excepcion no manejada en una respuesta 500 JSON -- no
            # propaga como excepcion de Python al test client. Eso NO
            # afecta el rollback: `transaction.atomic()` revierte apenas
            # la excepcion sale del `with`, mucho antes de que DRF la
            # atrape para armar la respuesta.
            response = self.client.patch(
                f"/api/v1/visits/{self.visit.id_visit}/vitals",
                self._valid_edit_payload(weightKg=99),
                format="json",
                HTTP_X_REQUEST_ID=self.request_id,
                **self._csrf_headers(),
            )
            self.assertEqual(response.status_code, 500)

        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertEqual(
            float(row.weight_kg),
            70.0,
            "La correccion NO debe persistir si su auditoria fallo (rollback D10).",
        )
        self.assertIsNone(row.updated_by_id)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="VitalsEdited").count(), 0)


class VitalsEditAttributionTests(VitalsEditApiTestsBase):
    def test_correction_keeps_original_captured_by_and_sets_updated_by(self):
        self._capture_as(self.captor)

        self._login_as(self.editor.usuario)
        response = self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_edit_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertEqual(row.captured_by_id, self.captor.id_usuario)
        self.assertEqual(row.updated_by_id, self.editor.id_usuario)

        self.assertEqual(
            response.data["vitals"]["capturedBy"]["id"], self.captor.id_usuario
        )
        self.assertEqual(
            response.data["vitals"]["updatedBy"]["id"], self.editor.id_usuario
        )


class VitalsEditPermissionTests(VitalsEditApiTestsBase):
    def test_captor_without_edit_capability_gets_403_on_patch(self):
        self._capture_as(self.captor)

        self._login_as(self.captor.usuario)
        response = self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_edit_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        row = VisitVitalSigns.objects.get(id_visit=self.visit)
        self.assertIsNone(row.updated_by_id)
        self.assertEqual(float(row.weight_kg), 70.0)

    def test_doctor_capability_gets_403_on_post_and_patch(self):
        self._login_as(self.doctor.usuario)

        post_response = self.client.post(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_capture_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

        self._capture_as(self.captor)
        self._login_as(self.doctor.usuario)
        patch_response = self.client.patch(
            f"/api/v1/visits/{self.visit.id_visit}/vitals",
            self._valid_edit_payload(),
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
            **self._csrf_headers(),
        )
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
