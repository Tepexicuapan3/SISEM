"""
Suite de auditoria para `cirugias` (change `auditoria-cirugias-ambulancias`).

Cubre las 2 acciones de este dominio (diseño #512, PARTE B / Testing Strategy):
- `SurgeryScheduled` (SIMPLE): log_event tras `schedule_surgery`, sin
  `raise_on_error` -- un fallo de auditoria NO bloquea el alta.
- `SurgeryCancelled` (ESTRICTO): `audit_hook` dentro de `transaction.atomic()`
  con `raise_on_error=True` -- un fallo de auditoria revierte la cancelacion.

`setUp` clonado de `test_surgery_schedule_api.py:16-83` + `CatMotivoCancelacionCirugia`.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import (
    CatClasificacionCirugia,
    CatMotivoCancelacionCirugia,
    CatTipoCirugia,
    Permisos,
    Roles,
)
from apps.cirugias.models import SurgerySchedule
from apps.medicos.models import CatMedico

JSON_PRIMITIVES = (str, int, float, bool, type(None))


class SurgeryAuditApiTests(APITestCase):
    def setUp(self):
        self.request_id = "77777777-7777-7777-7777-777777777777"
        self.writer_password = "Writer_123456"

        self._create_user_with_role(
            username="cirugias_audit_writer",
            email="cirugias.audit.writer@example.com",
            password=self.writer_password,
            role_code="CIRUGIAS_AUDIT_WRITER",
            permissions=["clinico:cirugias:write", "clinico:cirugias:read"],
        )
        self.writer = SyUsuario.objects.get(usuario="cirugias_audit_writer")

        self.surgeon = CatMedico.objects.create(nombre_display="Dr. Auditoria")
        self.surgery_type = CatTipoCirugia.objects.create(name="Apendicectomia")
        self.classification = CatClasificacionCirugia.objects.create(name="Cirugia corta")
        self.reason = CatMotivoCancelacionCirugia.objects.create(name="Paciente no se presento")

        self.tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    def _create_user_with_role(self, username, email, password, role_code, permissions):
        user = SyUsuario.objects.create(
            usuario=username, correo=email, clave_hash=make_password(password),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, paterno="Test", materno="User")
        role, _ = Roles.objects.get_or_create(
            rol=role_code, defaults={"desc_rol": f"Rol {role_code}", "landing_route": "/reportes"},
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        for permission_code in permissions:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code, defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": username, "password": password},
            format="json", HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def _csrf_headers(self):
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _payload(self, **overrides):
        payload = {
            "noExp": "EXP-A001",
            "pkNum": 0,
            "surgeonId": self.surgeon.id,
            "surgeryTypeId": self.surgery_type.id,
            "classificationId": self.classification.id,
            "scheduledDate": self.tomorrow,
            "scheduledTime": "09:00:00",
            "durationMinutes": 60,
            "cieCodes": [],
        }
        payload.update(overrides)
        return payload

    def _schedule(self, **overrides):
        self._login_as("cirugias_audit_writer", self.writer_password)
        return self.client.post(
            "/api/v1/surgeries", self._payload(**overrides), format="json",
            **self._csrf_headers(),
        )

    def _cancel(self, surgery_id, **payload):
        return self.client.patch(
            f"/api/v1/surgeries/{surgery_id}/cancel", payload, format="json",
            **self._csrf_headers(),
        )

    # ------------------------------------------------------------------
    # SurgeryScheduled (SIMPLE)
    # ------------------------------------------------------------------

    def test_schedule_writes_audit_event(self):
        response = self._schedule()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        events = AuditoriaEvento.objects.filter(accion="SurgeryScheduled")
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.recurso_tipo, "cirugias")
        self.assertEqual(event.recurso_id, response.data["id"])
        self.assertEqual(event.actor_usuario_id, self.writer.id_usuario)
        self.assertEqual(event.resultado, "SUCCESS")
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["status"], "activa")
        self.assertEqual(event.datos_despues["scheduledDate"], self.tomorrow)
        self.assertEqual(event.datos_despues["surgeonId"], self.surgeon.id)
        self.assertEqual(event.datos_despues["surgeryTypeId"], self.surgery_type.id)
        self.assertEqual(event.datos_despues["classificationId"], self.classification.id)
        self.assertEqual(event.datos_despues["cieCodesCount"], 0)
        self.assertEqual(event.meta["module"], "cirugias")
        self.assertEqual(event.meta["folio"], response.data["folio"])

    def test_schedule_persists_even_if_audit_fails(self):
        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            response = self._schedule()

        # SIMPLE: la respuesta clinica no se bloquea por un fallo del logger.
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            SurgerySchedule.objects.filter(pk=response.data["id"]).exists(),
        )
        self.assertEqual(AuditoriaEvento.objects.filter(accion="SurgeryScheduled").count(), 0)

    # ------------------------------------------------------------------
    # SurgeryCancelled (ESTRICTO)
    # ------------------------------------------------------------------

    def test_cancel_writes_audit_event(self):
        created = self._schedule()
        surgery_id = created.data["id"]

        response = self._cancel(
            surgery_id, reasonId=self.reason.id, notes="No se presento a la cita",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        events = AuditoriaEvento.objects.filter(accion="SurgeryCancelled")
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.recurso_tipo, "cirugias")
        self.assertEqual(event.recurso_id, surgery_id)
        self.assertEqual(event.actor_usuario_id, self.writer.id_usuario)
        self.assertEqual(event.resultado, "SUCCESS")
        self.assertEqual(event.datos_antes, {"status": "activa"})
        self.assertEqual(event.datos_despues["status"], "cancelada")
        self.assertEqual(event.datos_despues["reasonId"], self.reason.id)
        self.assertEqual(event.datos_despues["reasonName"], self.reason.name)
        self.assertEqual(event.datos_despues["notes"], "No se presento a la cita")
        self.assertEqual(event.meta["folio"], created.data["folio"])

    def test_cancel_audit_failure_rolls_back(self):
        created = self._schedule()
        surgery_id = created.data["id"]

        with patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            # El EXCEPTION_HANDLER global convierte la excepcion en 500 JSON
            # -- no propaga como excepcion de Python al test client. El
            # rollback ocurre igual: `transaction.atomic()` revierte apenas
            # la excepcion sale del `with`, antes de que DRF arme la
            # respuesta (mismo patron que `test_vitals_edit_api.py:241-269`).
            response = self._cancel(
                surgery_id, reasonId=self.reason.id, notes="No se presento",
            )

        self.assertEqual(response.status_code, 500)

        surgery = SurgerySchedule.objects.get(pk=surgery_id)
        self.assertEqual(surgery.status, SurgerySchedule.Status.ACTIVA)
        self.assertEqual(surgery.cancellations.count(), 0)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="SurgeryCancelled").count(), 0)

    def test_already_cancelled_guard_writes_no_event(self):
        created = self._schedule()
        surgery_id = created.data["id"]

        first = self._cancel(surgery_id, reasonId=self.reason.id)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(AuditoriaEvento.objects.filter(accion="SurgeryCancelled").count(), 1)

        repeat = self._cancel(surgery_id, reasonId=self.reason.id)
        self.assertEqual(repeat.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(repeat.data["code"], "SURGERY_ALREADY_CANCELLED")
        # La guarda corre antes del hook -- el conteo no debe subir.
        self.assertEqual(AuditoriaEvento.objects.filter(accion="SurgeryCancelled").count(), 1)

    # ------------------------------------------------------------------
    # Regla transversal D4: payload JSON-safe
    # ------------------------------------------------------------------

    def _assert_json_primitive_tree(self, value, path):
        if isinstance(value, dict):
            for key, sub_value in value.items():
                self._assert_json_primitive_tree(sub_value, f"{path}.{key}")
        elif isinstance(value, list):
            for index, sub_value in enumerate(value):
                self._assert_json_primitive_tree(sub_value, f"{path}[{index}]")
        else:
            self.assertIsInstance(
                value, JSON_PRIMITIVES,
                f"{path} no es JSON-safe: {value!r} ({type(value)})",
            )

    def test_audit_payload_is_json_primitive(self):
        created = self._schedule()
        surgery_id = created.data["id"]

        cancel = self._cancel(
            surgery_id, reasonId=self.reason.id, notes="Motivo de prueba",
        )
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)

        events = AuditoriaEvento.objects.filter(
            accion__in=["SurgeryScheduled", "SurgeryCancelled"],
        )
        self.assertEqual(events.count(), 2)
        for event in events:
            self._assert_json_primitive_tree(event.datos_antes, f"{event.accion}.datos_antes")
            self._assert_json_primitive_tree(event.datos_despues, f"{event.accion}.datos_despues")
