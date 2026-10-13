"""
Tests de contrato para el check-in manual (sin QR): búsqueda de candidatos
por nombre/folio y confirmación de check-in por folio directo.

Mismo patrón de setUp (usuario + rol + permisos vía ORM, login real por
cookie/CSRF) que ``apps.recepcion.tests.test_visit_contract_api``.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles
from apps.medicos.models import CatMedico
from apps.recepcion.models import CitaMedica, EstatusCita, Visit

# Mismo no_exp/nombre reales usados en la verificación manual de esta tarea
# contra el servidor real (empleado #40041). Acá se mockea ``buscar_expediente``
# -- el alias de BD "expedientes" NO existe bajo ``manage.py test``
# (config/settings.py reemplaza DATABASES por un único sqlite ":memory:"
# cuando "test" está en sys.argv, ver también el mismo mock en
# apps/portal_citas/tests/test_portal_endpoints.py para el mismo motivo).
PACIENTE_NO_EXP = "40041"
PACIENTE_NOMBRE_ESPERADO = "HERNANDEZ ROMERO ANA LAURA"
PACIENTE_EXPEDIENTE_MOCK = {
    "empleados": [
        {"PK_NUM": 0, "DS_PATERNO": "HERNANDEZ", "DS_MATERNO": "ROMERO", "DS_NOMBRE": "ANA LAURA"},
    ],
    "familiares": [],
}


class CheckinManualApiTests(APITestCase):
    def setUp(self):
        expediente_patcher = mock.patch(
            "apps.recepcion.uses_case.qr_checkin_usecase.buscar_expediente",
            return_value=PACIENTE_EXPEDIENTE_MOCK,
        )
        self.addCleanup(expediente_patcher.stop)
        expediente_patcher.start()

        self.request_id = "22222222-2222-2222-2222-222222222222"
        self.recepcion_password = "Recep_123456"

        self._create_user_with_role(
            username="recepcion_checkin_user",
            email="recepcion_checkin@example.com",
            password=self.recepcion_password,
            role_code="RECEPCION_CHECKIN",
            permissions=[
                "recepcion:citas:read",
                "recepcion:fichas:medicina_general:read",
                "recepcion:fichas:medicina_general:create",
            ],
        )

        medico_user = SyUsuario.objects.create(
            usuario="medico_checkin_user", correo="medico_checkin@example.com",
            clave_hash=make_password("Medico_123456"), est_activo=True,
            cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=medico_user, nombre="Medico", paterno="Checkin", materno="Test",
        )
        self.medico = CatMedico.objects.create(id_usuario=medico_user)

        self._login_as("recepcion_checkin_user", self.recepcion_password)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _create_user_with_role(self, username, email, password, role_code, permissions=None):
        user = SyUsuario.objects.create(
            usuario=username, correo=email, clave_hash=make_password(password),
            est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user, nombre=username, paterno="Test", materno="User",
        )
        role = Roles.objects.create(
            rol=role_code, desc_rol=f"Rol {role_code}",
            landing_route="/recepcion", is_admin=False,
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        for permission_code in permissions or []:
            permission, _ = Permisos.objects.get_or_create(
                codigo=permission_code,
                defaults={"descripcion": permission_code, "is_active": True},
            )
            RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permission)
        return user

    def _login_as(self, username, password):
        self.client.cookies.clear()
        # ``login_user`` bloquea con SESSION_ALREADY_ACTIVE (409) si Redis ya
        # tiene una sesión activa para este user_id (``session_registry.
        # start_session(..., block_if_active=True)``). Redis vive fuera de la
        # transacción de test (que SQLite revierte por test), así que un
        # user_id reciclado entre tests puede arrastrar una sesión "activa"
        # de una corrida anterior. Se limpia proactivamente antes de cada
        # login para que el test sea idempotente sin depender del estado de
        # Redis entre corridas.
        user = SyUsuario.objects.filter(usuario=username).first()
        if user is not None:
            PolicyStore().clear_active_session(user.id_usuario)

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": username, "password": password},
            format="json",
            HTTP_X_REQUEST_ID=self.request_id,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies

    def _csrf_headers(self):
        csrf_token = self.client.cookies.get("csrf_token")
        if csrf_token is None:
            csrf_token = "csrf-token-test"
            self.client.cookies["csrf_token"] = csrf_token
        else:
            csrf_token = csrf_token.value
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _cita_hoy(self, **overrides):
        hoy = timezone.localtime(timezone.now())
        fecha_hora = overrides.pop("fecha_hora", hoy + timedelta(hours=2))
        defaults = dict(
            folio=CitaMedica.generar_folio(),
            no_exp=PACIENTE_NO_EXP, pk_num=0,
            medico_id=self.medico.id,
            fecha_hora=fecha_hora, duracion_min=20,
            servicio_tipo="medicina_general", estatus=EstatusCita.AGENDADA,
            motivo="Test check-in manual",
        )
        defaults.update(overrides)
        return CitaMedica.objects.create(**defaults)

    # ── candidatos ───────────────────────────────────────────────────────

    def test_candidatos_por_nombre_encuentra_cita_de_hoy(self):
        cita = self._cita_hoy()

        response = self.client.get(
            "/api/v1/citas/checkin/candidatos", {"nombre": "hernandez"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        folios = [c["folio"] for c in response.data["candidatos"]]
        self.assertIn(cita.folio, folios)
        candidato = next(c for c in response.data["candidatos"] if c["folio"] == cita.folio)
        self.assertEqual(candidato["pacienteNombre"], PACIENTE_NOMBRE_ESPERADO)
        self.assertEqual(candidato["origenCanal"], "RECEPCION")
        self.assertEqual(candidato["estatus"], EstatusCita.AGENDADA)

    def test_candidatos_por_folio_exacto(self):
        cita = self._cita_hoy()
        self._cita_hoy(folio=CitaMedica.generar_folio())  # otra cita, no debe aparecer

        response = self.client.get(
            "/api/v1/citas/checkin/candidatos", {"folio": cita.folio},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["candidatos"]), 1)
        self.assertEqual(response.data["candidatos"][0]["folio"], cita.folio)

    def test_candidatos_excluye_cancelada_y_ya_verificada(self):
        cancelada = self._cita_hoy(estatus=EstatusCita.CANCELADA)
        ya_verificada = self._cita_hoy(verificado_en=timezone.now(), verificado_por_id=1)

        response = self.client.get(
            "/api/v1/citas/checkin/candidatos", {"nombre": "hernandez"},
        )

        folios = [c["folio"] for c in response.data["candidatos"]]
        self.assertNotIn(cancelada.folio, folios)
        self.assertNotIn(ya_verificada.folio, folios)

    def test_candidatos_ambos_parametros_devuelve_422(self):
        response = self.client.get(
            "/api/v1/citas/checkin/candidatos", {"nombre": "x", "folio": "CIT-1"},
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_candidatos_sin_parametros_devuelve_422(self):
        response = self.client.get("/api/v1/citas/checkin/candidatos")
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # ── confirmar-folio ──────────────────────────────────────────────────

    def test_confirmar_folio_crea_visita_y_marca_verificada(self):
        cita = self._cita_hoy()

        response = self.client.post(
            "/api/v1/citas/checkin/confirmar-folio",
            {"folio": cita.folio},
            format="json",
            **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["folio"], cita.folio)
        self.assertEqual(response.data["paciente"], PACIENTE_NOMBRE_ESPERADO)
        self.assertIsNotNone(response.data["visit"]["id"])

        cita.refresh_from_db()
        self.assertIsNotNone(cita.verificado_en)

        visit_exists = Visit.objects.filter(appointment_id=cita.folio).exists()
        self.assertTrue(visit_exists)

    def test_confirmar_folio_duplicado_devuelve_409(self):
        cita = self._cita_hoy()
        self.client.post(
            "/api/v1/citas/checkin/confirmar-folio",
            {"folio": cita.folio}, format="json", **self._csrf_headers(),
        )

        response = self.client.post(
            "/api/v1/citas/checkin/confirmar-folio",
            {"folio": cita.folio}, format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_confirmar_folio_inexistente_devuelve_404(self):
        response = self.client.post(
            "/api/v1/citas/checkin/confirmar-folio",
            {"folio": "CIT-NO-EXISTE"}, format="json", **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_confirmar_folio_sin_csrf_devuelve_403(self):
        cita = self._cita_hoy()
        response = self.client.post(
            "/api/v1/citas/checkin/confirmar-folio",
            {"folio": cita.folio}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
