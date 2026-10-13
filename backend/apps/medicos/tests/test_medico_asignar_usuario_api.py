"""POST /api/v1/medicos/<medico_id>/asignar-usuario (R9, S9.1-S9.4).

Mueve los datos personales de un CatMedico SIN usuario al DetUsuario /
DetUsuarioCedula, setea id_usuario y limpia los campos propios. Nunca pisa
datos del usuario. Mismo mecanismo de auth que `test_medico_create_api.py`."""

from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, DetUsuarioCedula, SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import CatTipoPersonal, Escuelas, Permisos, Roles
from apps.medicos import identity
from apps.medicos.models import CatMedico


class MedicoAsignarUsuarioApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.tipo_medico, _ = CatTipoPersonal.objects.get_or_create(
            name="Médico", defaults={"is_active": True}
        )
        self.tipo_admin, _ = CatTipoPersonal.objects.get_or_create(
            name="Administrativo", defaults={"is_active": True}
        )
        self.role, _ = Roles.objects.get_or_create(
            rol="ADMIN_MEDICOS_ASIGNAR_TEST",
            defaults={"desc_rol": "Admin medicos asignar (test)", "landing_route": "/admin"},
        )
        permiso, _ = Permisos.objects.get_or_create(
            codigo="admin:gestion:medicos:update",
            defaults={"descripcion": "Actualizar medicos", "is_active": True},
        )
        RelRolPermiso.objects.get_or_create(id_rol=self.role, id_permiso=permiso)

        self.actor = self._create_user("admin_asignar", tipo=self.tipo_admin)
        RelUsuarioRol.objects.create(id_usuario=self.actor, id_rol=self.role, is_primary=True)
        self.auth_headers = self._auth_headers(self.actor)

        self.medico = CatMedico.objects.create(
            id=512, nombre="JUAN", paterno="LOPEZ", materno="RAMIREZ", cedula_profesional="CED-1",
        )

    def _create_user(self, username, tipo, nombre=None, paterno=None, materno=None):
        user = SyUsuario.objects.create(
            usuario=username,
            correo=f"{username}@example.com",
            clave_hash=make_password("x"),
            est_activo=True,
        )
        DetUsuario.objects.create(
            id_usuario=user,
            nombre=nombre if nombre is not None else username,
            paterno=paterno,
            materno=materno,
            id_tipo_personal=tipo,
        )
        return user

    def _auth_headers(self, user):
        access, _refresh, _sid = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access
        csrf_token = "csrf-token-test"
        self.client.cookies["csrf_token"] = csrf_token
        return {"HTTP_X_CSRF_TOKEN": csrf_token}

    def _post(self, medico_id, usuario_id):
        body = {} if usuario_id is None else {"usuarioId": usuario_id}
        return self.client.post(
            f"/api/v1/medicos/{medico_id}/asignar-usuario", body, format="json", **self.auth_headers,
        )

    # ── Camino feliz (S9.1) ─────────────────────────────────────────────────

    def test_mueve_nombres_y_cedula_y_limpia_el_medico(self):
        user = self._create_user("dr_nuevo", self.tipo_medico, nombre="")
        det = user.detalle
        det.nombre = ""
        det.save()

        response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["id"], 512)
        self.assertEqual(response.data["usuarioId"], user.id_usuario)
        self.assertTrue(response.data["tieneUsuario"])
        self.assertEqual(response.data["descartados"], {})

        self.medico.refresh_from_db()
        self.assertEqual(self.medico.id, 512)
        self.assertEqual(self.medico.id_usuario_id, user.id_usuario)
        for campo in ("nombre", "paterno", "materno", "cedula_profesional"):
            self.assertIsNone(getattr(self.medico, campo), campo)
        self.assertEqual(self.medico.updated_by_id, self.actor.id_usuario)

        det.refresh_from_db()
        self.assertEqual((det.nombre, det.paterno, det.materno), ("JUAN", "LOPEZ", "RAMIREZ"))
        cedula = DetUsuarioCedula.objects.get(id_usuario=user)
        self.assertEqual(
            (cedula.numero, cedula.tipo, cedula.es_principal, cedula.orden),
            ("CED-1", "PROFESIONAL", True, 1),
        )

    def test_no_pisa_nombres_del_usuario_y_los_reporta_como_descartados(self):
        user = self._create_user(
            "dr_con_nombre", self.tipo_medico, nombre="ANA", paterno="PEREZ", materno=None,
        )

        response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        det = DetUsuario.objects.get(pk=user.id_usuario)
        # Lo que el usuario ya tenia se conserva; solo se llena el vacio (materno).
        self.assertEqual((det.nombre, det.paterno, det.materno), ("ANA", "PEREZ", "RAMIREZ"))
        self.assertEqual(response.data["descartados"], {"nombre": "JUAN", "paterno": "LOPEZ"})
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.nombre)
        self.assertIsNone(self.medico.paterno)

    def test_nombre_igual_no_se_reporta_como_descartado(self):
        user = self._create_user(
            "dr_igual", self.tipo_medico, nombre="JUAN", paterno="LOPEZ", materno="RAMIREZ",
        )
        response = self._post(self.medico.id, user.id_usuario)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["descartados"], {})

    def test_no_toca_cedulas_si_el_usuario_ya_tiene(self):
        user = self._create_user("dr_con_cedula", self.tipo_medico)
        DetUsuarioCedula.objects.create(
            id_usuario=user, numero="PROPIA-9", tipo="ESPECIALIDAD", es_principal=True, orden=1,
        )

        response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            list(DetUsuarioCedula.objects.filter(id_usuario=user).values_list("numero", "tipo")),
            [("PROPIA-9", "ESPECIALIDAD")],
        )
        # El nombre del usuario (su username) tambien difiere y se conserva.
        self.assertEqual(
            response.data["descartados"], {"nombre": "JUAN", "cedulaProfesional": "CED-1"}
        )
        self.medico.refresh_from_db()
        # Igual se limpia: el CheckConstraint exige que no queden datos propios.
        self.assertIsNone(self.medico.cedula_profesional)
        self.assertEqual(self.medico.id_usuario_id, user.id_usuario)

    def test_mueve_la_escuela_si_el_usuario_no_tiene(self):
        esc = Escuelas.objects.create(code="UNAM", name="Universidad Nacional")
        CatMedico.objects.filter(pk=512).update(id_escuela=esc)
        user = self._create_user("dr_sin_escuela", self.tipo_medico)

        response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(DetUsuario.objects.get(pk=user.id_usuario).id_escuela_id, esc.id)
        self.assertEqual(response.data["escuela"]["id"], esc.id)
        self.assertNotIn("escuelaId", response.data["descartados"])
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.id_escuela_id)

    def test_no_pisa_la_escuela_del_usuario_y_la_reporta(self):
        propia = Escuelas.objects.create(code="IPN", name="Instituto Politecnico")
        del_medico = Escuelas.objects.create(code="UNAM", name="Universidad Nacional")
        CatMedico.objects.filter(pk=512).update(id_escuela=del_medico)
        user = self._create_user("dr_con_escuela", self.tipo_medico)
        DetUsuario.objects.filter(pk=user.id_usuario).update(id_escuela=propia)

        response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(DetUsuario.objects.get(pk=user.id_usuario).id_escuela_id, propia.id)
        self.assertEqual(response.data["descartados"]["escuelaId"], del_medico.id)
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.id_escuela_id)

    def test_mueve_sexo_y_fecha_nac_y_no_pisa_los_del_usuario(self):
        CatMedico.objects.filter(pk=512).update(sexo="M", fecha_nac="1975-03-15")
        user = self._create_user("dr_sexo", self.tipo_medico)
        # El usuario ya tiene sexo (se conserva) pero no fecha (se llena).
        DetUsuario.objects.filter(pk=user.id_usuario).update(sexo="F")

        response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        det = DetUsuario.objects.get(pk=user.id_usuario)
        self.assertEqual((det.sexo, str(det.fecha_nac)), ("F", "1975-03-15"))
        self.assertEqual(response.data["descartados"]["sexo"], "M")
        self.assertNotIn("fechaNac", response.data["descartados"])
        self.assertEqual(response.data["fechaNac"], "1975-03-15")
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.sexo)
        self.assertIsNone(self.medico.fecha_nac)

    def test_medico_sin_datos_personales_solo_asigna(self):
        vacio = CatMedico.objects.create(id=700)
        user = self._create_user("dr_vacio", self.tipo_medico)

        response = self._post(vacio.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        vacio.refresh_from_db()
        self.assertEqual(vacio.id_usuario_id, user.id_usuario)
        self.assertFalse(DetUsuarioCedula.objects.filter(id_usuario=user).exists())

    def test_invalida_cache_de_identidad(self):
        user = self._create_user("dr_cache", self.tipo_medico)
        # Se cachea "este medico no tiene usuario" / "este usuario no es medico".
        self.assertIsNone(identity.usuario_id_for_medico(512))
        self.assertIsNone(identity.medico_id_for_usuario(user.id_usuario))

        with self.captureOnCommitCallbacks(execute=True):
            response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(identity.usuario_id_for_medico(512), user.id_usuario)
        self.assertEqual(identity.medico_id_for_usuario(user.id_usuario), 512)

    # ── Validaciones ────────────────────────────────────────────────────────

    def test_medico_inexistente_404(self):
        user = self._create_user("dr_x", self.tipo_medico)
        response = self._post(99999, user.id_usuario)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "MEDICO_NOT_FOUND")

    def test_medico_que_ya_tiene_usuario_409(self):  # S9.4
        dueno = self._create_user("dueno", self.tipo_medico)
        con_usuario = CatMedico.objects.create(id=800, id_usuario=dueno)
        otro = self._create_user("otro_medico", self.tipo_medico)

        response = self._post(con_usuario.id, otro.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "MEDICO_YA_TIENE_USUARIO")
        con_usuario.refresh_from_db()
        self.assertEqual(con_usuario.id_usuario_id, dueno.id_usuario)

    def test_usuario_inexistente_404(self):
        response = self._post(self.medico.id, 999999)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "USER_NOT_FOUND")

    def test_sin_usuario_id_400(self):
        response = self._post(self.medico.id, None)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_usuario_no_medico_400(self):
        user = self._create_user("administrativo", self.tipo_admin)
        response = self._post(self.medico.id, user.id_usuario)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "TIPO_PERSONAL_INVALIDO")
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.id_usuario_id)
        self.assertEqual(self.medico.nombre, "JUAN")

    def test_usuario_ya_asignado_a_otro_medico_409(self):  # S9.3
        user = self._create_user("ya_medico", self.tipo_medico)
        CatMedico.objects.create(id=900, id_usuario=user)

        response = self._post(self.medico.id, user.id_usuario)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "MEDICO_EXISTS")
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.id_usuario_id)
        self.assertEqual(self.medico.cedula_profesional, "CED-1")

    # ── Atomicidad (S9.2) ───────────────────────────────────────────────────

    def test_fallo_al_crear_cedula_hace_rollback_total(self):
        user = self._create_user("dr_rollback", self.tipo_medico, nombre="")
        det = user.detalle
        det.nombre = ""
        det.save()

        with patch(
            "apps.medicos.uses_case.medico_usecase.DetUsuarioCedula.objects.create",
            side_effect=RuntimeError("falla simulada"),
        ):
            self.client.raise_request_exception = False
            response = self._post(self.medico.id, user.id_usuario)

        self.assertGreaterEqual(response.status_code, 500)
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.id_usuario_id)
        self.assertEqual(self.medico.nombre, "JUAN")
        self.assertEqual(self.medico.cedula_profesional, "CED-1")
        det.refresh_from_db()
        self.assertEqual(det.nombre, "")  # el llenado de nombres tambien se revirtio

    # ── Permisos ────────────────────────────────────────────────────────────

    def test_sin_permiso_update_403(self):
        RelRolPermiso.objects.filter(id_rol=self.role).delete()
        user = self._create_user("dr_perm", self.tipo_medico)
        response = self._post(self.medico.id, user.id_usuario)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.medico.refresh_from_db()
        self.assertIsNone(self.medico.id_usuario_id)
