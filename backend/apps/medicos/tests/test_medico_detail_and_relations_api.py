"""Cobertura para los sub-recursos de /api/v1/medicos que no tenian NINGUNA
prueba: PATCH del medico, especialidades, centros y excepciones (incluye el
efecto secundario de actualizar estatus_medico al registrar una excepcion
de vacaciones/incapacidad/suspension)."""

from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import CatCentroAtencion, CatTipoPersonal, Especialidades, Permisos, Roles
from apps.medicos.models import CatMedico, RelMedicoCentro, RelMedicoEspecialidad, RelMedicoExcepcion

MEDICOS_URL = "/api/v1/medicos"


class MedicoDetailAndRelationsApiTestsBase(APITestCase):
    PERMISOS = ()

    def setUp(self):
        self.tipo_medico, _ = CatTipoPersonal.objects.get_or_create(
            name="Médico", defaults={"is_active": True}
        )

        self.role, _ = Roles.objects.get_or_create(
            rol=f"ROLE_{self.__class__.__name__}",
            defaults={"desc_rol": "Rol de test", "landing_route": "/admin"},
        )
        for code in self.PERMISOS:
            permiso, _ = Permisos.objects.get_or_create(
                codigo=code, defaults={"descripcion": code, "is_active": True}
            )
            RelRolPermiso.objects.get_or_create(id_rol=self.role, id_permiso=permiso)

        self.actor = self._create_user("admin_actor")
        self.auth_headers = self._auth_headers(self.actor)

        self.medico_user = self._create_user("medico_test", tipo_personal=self.tipo_medico)
        self.medico = CatMedico.objects.create(id_usuario=self.medico_user)

    def _create_user(self, username, tipo_personal=None):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("x"),
            est_activo=True,
        )
        DetUsuario.objects.create(
            id_usuario=user, nombre=username, paterno="Test", materno="User",
            id_tipo_personal=tipo_personal,
        )
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=self.role, is_primary=True)
        return user

    def _auth_headers(self, user):
        access, _refresh, _sid = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}


class MedicoPatchApiTests(MedicoDetailAndRelationsApiTestsBase):
    PERMISOS = ("admin:gestion:medicos:read", "admin:gestion:medicos:update")

    def test_patch_updates_editable_fields(self):
        response = self.client.patch(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}",
            {
                "tipoMedico": "HOSPITAL",
                "servicio": "Urgencias",
                "observaciones": "Nota de prueba",
                "estatusMedico": "VACACIONES",
            },
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.medico.refresh_from_db()
        self.assertEqual(self.medico.tipo_medico, "HOSPITAL")
        self.assertEqual(self.medico.servicio, "Urgencias")
        self.assertEqual(self.medico.estatus_medico, "VACACIONES")

    def test_patch_not_found(self):
        response = self.client.patch(
            f"{MEDICOS_URL}/999999",
            {"servicio": "X"},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "MEDICO_NOT_FOUND")

    def test_get_detail_resolves_by_real_medico_pk(self):
        response = self.client.get(f"{MEDICOS_URL}/{self.medico.id}", **self.auth_headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["medico"]["medicoId"], self.medico.id)


class MedicoEspecialidadesApiTests(MedicoDetailAndRelationsApiTestsBase):
    PERMISOS = ("admin:gestion:medicos:update",)

    def setUp(self):
        super().setUp()
        self.especialidad = Especialidades.objects.create(name="Cardiología")
        self.especialidad_2 = Especialidades.objects.create(name="Pediatría")

    def test_post_especialidad_creates_relation(self):
        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/especialidades",
            {"especialidadId": self.especialidad.id, "esPrincipal": True},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            RelMedicoEspecialidad.objects.filter(
                medico=self.medico, especialidad=self.especialidad, es_principal=True
            ).exists()
        )

    def test_post_especialidad_principal_unsets_previous_principal(self):
        RelMedicoEspecialidad.objects.create(
            medico=self.medico, especialidad=self.especialidad, es_principal=True
        )

        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/especialidades",
            {"especialidadId": self.especialidad_2.id, "esPrincipal": True},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            RelMedicoEspecialidad.objects.get(
                medico=self.medico, especialidad=self.especialidad
            ).es_principal
        )
        self.assertTrue(
            RelMedicoEspecialidad.objects.get(
                medico=self.medico, especialidad=self.especialidad_2
            ).es_principal
        )

    def test_post_especialidad_rejects_unknown_especialidad(self):
        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/especialidades",
            {"especialidadId": 999999},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ESPECIALIDAD_NOT_FOUND")

    def test_delete_especialidad_removes_relation(self):
        RelMedicoEspecialidad.objects.create(medico=self.medico, especialidad=self.especialidad)

        response = self.client.delete(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/especialidades/{self.especialidad.id}",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            RelMedicoEspecialidad.objects.filter(
                medico=self.medico, especialidad=self.especialidad
            ).exists()
        )


class MedicoCentrosApiTests(MedicoDetailAndRelationsApiTestsBase):
    PERMISOS = ("admin:gestion:medicos:update",)

    def setUp(self):
        super().setUp()
        self.centro = CatCentroAtencion.objects.create(
            name="Centro Medicos Test",
            code="CMT-001",
            center_type=CatCentroAtencion.TipoCentro.CLINICA,
            is_external=False,
            address="Calle Uno 1",
            is_active=True,
            created_by_id=self.actor.id_usuario,
        )

    def test_post_centro_creates_relation(self):
        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/centros",
            {
                "centroId": self.centro.id,
                "tipoAdscripcion": "DEFINITIVA",
                "fechaInicio": str(date.today()),
            },
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            RelMedicoCentro.objects.filter(medico=self.medico, centro=self.centro).exists()
        )

    def test_post_centro_rejects_unknown_centro(self):
        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/centros",
            {"centroId": 999999, "fechaInicio": str(date.today())},
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "CENTRO_NOT_FOUND")

    def test_delete_centro_deactivates_instead_of_deleting(self):
        rel = RelMedicoCentro.objects.create(
            medico=self.medico, centro=self.centro, fecha_inicio=date.today() - timedelta(days=10),
        )

        response = self.client.delete(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/centros/{rel.id}",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rel.refresh_from_db()
        self.assertFalse(rel.is_active)
        self.assertEqual(rel.fecha_fin, date.today())


class MedicoExcepcionesApiTests(MedicoDetailAndRelationsApiTestsBase):
    PERMISOS = ("admin:gestion:medicos:read", "admin:gestion:medicos:excepciones")

    def test_post_excepcion_creates_and_lists(self):
        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/excepciones",
            {
                "tipo": "PERMISO",
                "fechaInicio": str(date.today()),
                "fechaFin": str(date.today() + timedelta(days=1)),
                "motivo": "Trámite personal",
            },
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        list_response = self.client.get(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/excepciones", **self.auth_headers
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["items"]), 1)
        self.assertEqual(list_response.data["items"][0]["tipo"], "PERMISO")

    def test_post_excepcion_vacaciones_updates_estatus_medico(self):
        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/excepciones",
            {
                "tipo": "VACACIONES",
                "fechaInicio": str(date.today()),
                "fechaFin": str(date.today() + timedelta(days=10)),
            },
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.medico.refresh_from_db()
        self.assertEqual(self.medico.estatus_medico, "VACACIONES")

    def test_post_excepcion_permiso_does_not_change_estatus_medico(self):
        estatus_original = self.medico.estatus_medico

        response = self.client.post(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/excepciones",
            {
                "tipo": "PERMISO",
                "fechaInicio": str(date.today()),
                "fechaFin": str(date.today()),
            },
            format="json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.medico.refresh_from_db()
        self.assertEqual(self.medico.estatus_medico, estatus_original)

    def test_delete_excepcion_deactivates(self):
        excepcion = RelMedicoExcepcion.objects.create(
            medico=self.medico, tipo="PERMISO",
            fecha_inicio=date.today(), fecha_fin=date.today(),
        )

        response = self.client.delete(
            f"{MEDICOS_URL}/{self.medico_user.id_usuario}/excepciones/{excepcion.id}",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        excepcion.refresh_from_db()
        self.assertFalse(excepcion.is_active)
