"""Cobertura para /api/v1/coberturas -- antes de estos tests el endpoint
solo tenia POST (crear), sin GET (listar) ni DELETE (cancelar), y sin
ninguna prueba en absoluto. Estos tests fijan el contrato de los 3 verbos."""

from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import CatCentroAtencion, Consultorios, Permisos, Roles, Turnos
from apps.medicos.models import CatMedico, RelMedicoCobertura

COBERTURAS_URL = "/api/v1/coberturas"


class MedicoCoberturasApiTests(APITestCase):
    def setUp(self):
        self.role, _ = Roles.objects.get_or_create(
            rol="ADMIN_COBERTURAS_TEST",
            defaults={"desc_rol": "Admin coberturas (test)", "landing_route": "/admin"},
        )
        for code, desc in [
            ("admin:gestion:medicos:read", "Leer medicos"),
            ("admin:gestion:medicos:coberturas", "Gestionar coberturas"),
        ]:
            permiso, _ = Permisos.objects.get_or_create(
                codigo=code, defaults={"descripcion": desc, "is_active": True}
            )
            RelRolPermiso.objects.get_or_create(id_rol=self.role, id_permiso=permiso)

        self.actor = self._create_user("admin_coberturas")
        self.auth_headers = self._auth_headers(self.actor)

        self.suplente_user = self._create_user("dr_suplente")
        self.titular_user = self._create_user("dr_titular")
        self.suplente = CatMedico.objects.create(id_usuario=self.suplente_user)
        self.titular = CatMedico.objects.create(id_usuario=self.titular_user)

        self.centro = CatCentroAtencion.objects.create(
            name="Centro Coberturas",
            code="CC-001",
            center_type=CatCentroAtencion.TipoCentro.CLINICA,
            is_external=False,
            address="Calle Uno 1",
            is_active=True,
            created_by_id=self.actor.id_usuario,
        )
        self.turno = Turnos.objects.create(name="Matutino")
        self.consultorio = Consultorios.objects.create(
            name="Consultorio 1", numero=1, id_turn=self.turno, id_center=self.centro,
        )

    def _create_user(self, username):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("x"),
            est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre=username, paterno="Test", materno="User")
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=self.role, is_primary=True)
        return user

    def _auth_headers(self, user):
        access, _refresh, _sid = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _create_cobertura(self, **overrides):
        data = {
            "medico_suplente": self.suplente,
            "medico_titular": self.titular,
            "consultorio": self.consultorio,
            "centro": self.centro,
            "fecha_inicio": date.today(),
            "fecha_fin": date.today() + timedelta(days=5),
            "motivo": "VACACIONES",
            "created_by_id": self.actor.id_usuario,
        }
        data.update(overrides)
        return RelMedicoCobertura.objects.create(**data)

    def test_post_cobertura_creates_with_horarios(self):
        response = self.client.post(
            COBERTURAS_URL,
            {
                "medicoSuplenteId": self.suplente.id,
                "medicoTitularId": self.titular.id,
                "consultorioId": self.consultorio.id,
                "centroId": self.centro.id,
                "fechaInicio": str(date.today()),
                "fechaFin": str(date.today() + timedelta(days=5)),
                "motivo": "VACACIONES",
                "horarios": [
                    {"diaSemana": "LUNES", "horaInicio": "09:00", "horaFin": "13:00"},
                ],
            },
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["medicoSuplenteId"], self.suplente.id)
        self.assertEqual(response.data["medicoTitularId"], self.titular.id)
        self.assertEqual(len(response.data["horarios"]), 1)
        self.assertTrue(response.data["isActive"])

    def test_post_cobertura_rejects_when_medico_not_found(self):
        response = self.client.post(
            COBERTURAS_URL,
            {
                "medicoSuplenteId": 999999,
                "medicoTitularId": self.titular.id,
                "consultorioId": self.consultorio.id,
                "centroId": self.centro.id,
                "fechaInicio": str(date.today()),
                "fechaFin": str(date.today() + timedelta(days=5)),
            },
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "MEDICO_NOT_FOUND")

    def test_get_coberturas_includes_when_medico_is_suplente(self):
        self._create_cobertura()

        response = self.client.get(
            COBERTURAS_URL, {"medicoId": self.suplente.id}, **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["medicoSuplenteId"], self.suplente.id)

    def test_get_coberturas_includes_when_medico_is_titular(self):
        self._create_cobertura()

        response = self.client.get(
            COBERTURAS_URL, {"medicoId": self.titular.id}, **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["medicoTitularId"], self.titular.id)

    def test_get_coberturas_requires_medico_id(self):
        response = self.client.get(COBERTURAS_URL, **self.auth_headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_get_coberturas_excludes_inactive(self):
        cobertura = self._create_cobertura()
        cobertura.is_active = False
        cobertura.save(update_fields=["is_active"])

        response = self.client.get(
            COBERTURAS_URL, {"medicoId": self.suplente.id}, **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])

    def test_delete_cobertura_soft_cancels(self):
        cobertura = self._create_cobertura()

        response = self.client.delete(
            f"{COBERTURAS_URL}/{cobertura.id}", **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cobertura.refresh_from_db()
        self.assertFalse(cobertura.is_active)
        self.assertEqual(cobertura.fecha_fin, date.today())

    def test_delete_cobertura_preserves_earlier_fecha_fin(self):
        earlier_end = date.today() - timedelta(days=1)
        cobertura = self._create_cobertura(fecha_fin=earlier_end)

        response = self.client.delete(
            f"{COBERTURAS_URL}/{cobertura.id}", **self.auth_headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cobertura.refresh_from_db()
        self.assertEqual(cobertura.fecha_fin, earlier_end)

    def test_delete_cobertura_not_found(self):
        response = self.client.delete(f"{COBERTURAS_URL}/999999", **self.auth_headers)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
