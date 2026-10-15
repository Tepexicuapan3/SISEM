"""API authorizer-designations/ (S9, S10, S17 + CRUD, permisos, soft delete, auditoria)."""
from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import (
    CatCentroAtencion,
    CatPermiso,
    CatRol,
    DesignacionAlcance,
    DesignacionAutorizador,
)
from apps.catalogos.services.designacion_autorizador_service import puede_autorizar

from .designacion_factories import get_tipo, make_center, make_designation, make_user

URL = "/api/v1/authorizer-designations/"
PASSWORD = "Admin_123456"
TODAY = date.today()


def _login_client(username, permission_codes):
    role = CatRol.objects.create(
        rol=f"ROL_{username}", desc_rol="rol de prueba", landing_route="/admin", is_active=True
    )
    for code in permission_codes:
        perm, _ = CatPermiso.objects.get_or_create(
            codigo=code, defaults={"descripcion": code, "is_active": True}
        )
        RelRolPermiso.objects.create(id_rol=role, id_permiso=perm)

    user = SyUsuario.objects.create(
        usuario=username,
        correo=f"{username}@example.com",
        clave_hash=make_password(PASSWORD),
        est_activo=True,
        cambiar_clave=False,
        terminos_acept=True,
    )
    DetUsuario.objects.create(id_usuario=user, nombre="Admin", paterno=username, materno="")
    RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
    PolicyStore().clear_active_session(user.id_usuario)

    client = APIClient()
    response = client.post(
        "/api/v1/auth/login", {"username": username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK, response.content
    client.cookies = response.cookies
    client.defaults["HTTP_X_CSRF_TOKEN"] = response.cookies.get(CSRF_COOKIE).value
    return client, user


class _Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin, self.admin_user = _login_client(
            "adm_desig",
            ["admin:autorizadores:designacion:read", "admin:autorizadores:designacion:write"],
        )
        self.tipo = get_tipo()
        self.target = make_user()
        self.clinica = make_center(CatCentroAtencion.TipoCentro.CLINICA)
        self.hospital = make_center(CatCentroAtencion.TipoCentro.HOSPITAL)

    def payload(self, **overrides):
        data = {
            "userId": self.target.id_usuario,
            "tipoAutorizacionId": self.tipo.id,
            "cargo": "Director Medico",
            "fechaInicio": (TODAY - timedelta(days=1)).isoformat(),
            "alcance": {"centros": [self.clinica.id]},
        }
        data.update(overrides)
        return data


class DesignacionPermissionsTests(_Base):
    def test_sin_sesion_no_accede(self):
        response = APIClient().get(URL)
        self.assertIn(response.status_code, (401, 403))

    def test_solo_lectura_no_puede_escribir(self):
        reader, _ = _login_client("reader_desig", ["admin:autorizadores:designacion:read"])
        self.assertEqual(reader.get(URL).status_code, 200)
        response = reader.post(URL, self.payload(), format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "INSUFFICIENT_PERMISSIONS")
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)

    def test_sin_permiso_de_lectura_no_lista(self):
        nobody, _ = _login_client("nobody_desig", ["admin:autorizadores:designacion:write"])
        self.assertEqual(nobody.get(URL).status_code, 403)

    def test_permiso_del_catalogo_antiguo_ya_no_basta(self):
        legacy, _ = _login_client("legacy_desig", ["admin:catalogos:autorizadores:read"])
        self.assertEqual(legacy.get(URL).status_code, 403)


class DesignacionCreateTests(_Base):
    def test_crea_con_centros_y_tipos_y_devuelve_detalle(self):
        response = self.admin.post(
            URL,
            self.payload(
                oficio="OF-1",
                alcance={"centros": [self.clinica.id], "tiposCentro": ["HOSPITAL"]},
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.data["designation"]
        self.assertEqual(body["userId"], self.target.id_usuario)
        self.assertEqual(body["tipoAutorizacion"]["code"], "CN")
        self.assertEqual(body["oficio"], "OF-1")
        self.assertEqual([c["id"] for c in body["alcance"]["centros"]], [self.clinica.id])
        self.assertEqual(body["alcance"]["tiposCentro"], ["HOSPITAL"])
        self.assertFalse(body["alcance"]["global"])
        self.assertTrue(body["vigente"])
        # La politica ve la designacion recien creada.
        self.assertTrue(puede_autorizar(self.target.id_usuario, "CN", self.clinica.id))
        self.assertTrue(puede_autorizar(self.target.id_usuario, "CN", self.hospital.id))

    def test_no_modifica_la_adscripcion_del_usuario(self):
        detalle = self.target.detalle
        detalle.id_centro_atencion = self.hospital
        detalle.save()
        self.admin.post(URL, self.payload(), format="json")
        detalle.refresh_from_db()
        self.assertEqual(detalle.id_centro_atencion_id, self.hospital.id)

    def test_alcance_vacio_se_rechaza_y_no_equivale_a_global(self):
        response = self.admin.post(URL, self.payload(alcance={}), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)

    def test_global_mezclado_con_centros_se_rechaza(self):
        response = self.admin.post(
            URL,
            self.payload(alcance={"global": True, "centros": [self.clinica.id]}, fechaFin=(TODAY + timedelta(days=5)).isoformat()),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_fecha_fin_anterior_a_inicio_se_rechaza(self):
        response = self.admin.post(
            URL,
            self.payload(fechaInicio="2026-05-10", fechaFin="2026-05-09"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("fechaFin", response.data["details"])

    def test_referencias_inexistentes_se_rechazan(self):
        for overrides in (
            {"userId": 999999},
            {"tipoAutorizacionId": 999999},
            {"alcance": {"centros": [999999]}},
        ):
            response = self.admin.post(URL, self.payload(**overrides), format="json")
            self.assertEqual(response.status_code, 400, overrides)
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)

    def test_duplicado_activo_mismo_usuario_y_tipo_da_409(self):
        self.assertEqual(self.admin.post(URL, self.payload(), format="json").status_code, 201)
        response = self.admin.post(URL, self.payload(), format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "DESIGNATION_EXISTS")

    def test_crea_evento_de_auditoria(self):
        response = self.admin.post(URL, self.payload(), format="json")
        event = AuditoriaEvento.objects.get(accion="AuthorizerDesignationCreated")
        self.assertEqual(event.recurso_tipo, "designacion_autorizador")
        self.assertEqual(event.recurso_id, response.data["designation"]["id"])
        self.assertEqual(event.actor_usuario_id, self.admin_user.id_usuario)
        self.assertIsNone(event.datos_antes)
        self.assertEqual(event.datos_despues["alcance"]["centros"], [self.clinica.id])


class DesignacionGlobalTests(_Base):
    def global_payload(self, **overrides):
        data = self.payload(
            alcance={"global": True},
            fechaFin=(TODAY + timedelta(days=30)).isoformat(),
        )
        data.update(overrides)
        return data

    def test_s9_sin_permiso_global_da_403_y_no_guarda_nada(self):
        response = self.admin.post(URL, self.global_payload(), format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "GLOBAL_PERMISSION_REQUIRED")
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)
        self.assertEqual(DesignacionAlcance.objects.count(), 0)

    def test_s9_sin_permiso_y_sin_fecha_fin_sigue_siendo_403_no_400(self):
        response = self.admin.post(
            URL, self.payload(alcance={"global": True}), format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_s10_con_permiso_global_pero_sin_fecha_fin_se_rechaza(self):
        client, _ = _login_client(
            "adm_global",
            [
                "admin:autorizadores:designacion:read",
                "admin:autorizadores:designacion:write",
                "admin:autorizadores:designacion:global",
            ],
        )
        response = client.post(URL, self.payload(alcance={"global": True}), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "GLOBAL_REQUIRES_END_DATE")
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)

    def test_con_permiso_global_y_fecha_fin_crea_y_habilita_cualquier_centro(self):
        client, _ = _login_client(
            "adm_global2",
            [
                "admin:autorizadores:designacion:read",
                "admin:autorizadores:designacion:write",
                "admin:autorizadores:designacion:global",
            ],
        )
        response = client.post(URL, self.global_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.data["designation"]["alcance"]["global"])
        self.assertTrue(puede_autorizar(self.target.id_usuario, "CN", self.hospital.id))

    def test_admin_sin_permiso_global_no_puede_editar_una_designacion_global(self):
        designation = make_designation(
            self.target,
            self.tipo,
            end=TODAY + timedelta(days=10),
            scopes=[("GLOBAL", None)],
        )
        response = self.admin.put(
            f"{URL}{designation.id}/",
            self.payload(alcance={"centros": [self.clinica.id]}),
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        designation.refresh_from_db()
        self.assertEqual(designation.scopes.filter(is_active=True, scope_type="GLOBAL").count(), 1)


class DesignacionReadTests(_Base):
    def test_lista_paginada_con_filtros(self):
        make_designation(self.target, self.tipo, scopes=[("CENTRO", self.clinica)], position="Jefe de Unidad")
        other_tipo = get_tipo("ZZ", "Otro")
        make_designation(make_user(), other_tipo, scopes=[("TIPO_CENTRO", "CLINICA")], position="Subdirector")

        response = self.admin.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(len(response.data["items"]), 2)

        filtered = self.admin.get(URL, {"tipoAutorizacionId": other_tipo.id})
        self.assertEqual(filtered.data["total"], 1)
        self.assertEqual(filtered.data["items"][0]["cargo"], "Subdirector")

        searched = self.admin.get(URL, {"search": "Jefe"})
        self.assertEqual(searched.data["total"], 1)

        self.assertEqual(self.admin.get(URL, {"sortBy": "nope"}).status_code, 400)
        self.assertEqual(self.admin.get(URL, {"isActive": "maybe"}).status_code, 400)
        self.assertEqual(self.admin.get(URL, {"page": "x"}).status_code, 400)

    def test_detalle_y_404(self):
        d = make_designation(self.target, self.tipo, scopes=[("CENTRO", self.clinica)])
        ok = self.admin.get(f"{URL}{d.id}/")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["designation"]["id"], d.id)
        missing = self.admin.get(f"{URL}999999/")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.data["code"], "DESIGNATION_NOT_FOUND")


class DesignacionUpdateDeleteTests(_Base):
    def setUp(self):
        super().setUp()
        self.designation = make_designation(
            self.target,
            self.tipo,
            scopes=[("CENTRO", self.clinica), ("TIPO_CENTRO", "HOSPITAL")],
        )

    def test_put_reemplaza_alcance_con_baja_logica_y_conserva_items_iguales(self):
        kept = self.designation.scopes.get(scope_type="CENTRO")
        other = make_center()
        response = self.admin.put(
            f"{URL}{self.designation.id}/",
            self.payload(cargo="Nuevo cargo", alcance={"centros": [self.clinica.id, other.id]}),
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.data["designation"]
        self.assertEqual(body["cargo"], "Nuevo cargo")
        self.assertEqual(sorted(c["id"] for c in body["alcance"]["centros"]), sorted([self.clinica.id, other.id]))
        self.assertEqual(body["alcance"]["tiposCentro"], [])

        kept.refresh_from_db()
        self.assertTrue(kept.is_active)  # el item que no cambio conserva su id
        removed = self.designation.scopes.get(scope_type="TIPO_CENTRO")
        self.assertFalse(removed.is_active)
        self.assertIsNotNone(removed.deleted_at)  # baja logica, no DELETE
        self.assertFalse(puede_autorizar(self.target.id_usuario, "CN", self.hospital.id))

    def test_put_audita_antes_y_despues(self):
        self.admin.put(f"{URL}{self.designation.id}/", self.payload(cargo="X"), format="json")
        event = AuditoriaEvento.objects.get(accion="AuthorizerDesignationUpdated")
        self.assertEqual(event.datos_antes["cargo"], "Director")
        self.assertEqual(event.datos_despues["cargo"], "X")

    def test_put_404_y_validacion(self):
        self.assertEqual(self.admin.put(f"{URL}999999/", self.payload(), format="json").status_code, 404)
        self.assertEqual(
            self.admin.put(f"{URL}{self.designation.id}/", {"cargo": "x"}, format="json").status_code, 400
        )

    def test_put_no_puede_chocar_con_otra_designacion_activa(self):
        other_user = make_user()
        make_designation(other_user, self.tipo, scopes=[("CENTRO", self.clinica)])
        response = self.admin.put(
            f"{URL}{self.designation.id}/",
            self.payload(userId=other_user.id_usuario),
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_delete_es_baja_logica_y_revoca_la_autorizacion(self):
        self.assertTrue(puede_autorizar(self.target.id_usuario, "CN", self.clinica.id))
        response = self.admin.delete(f"{URL}{self.designation.id}/")
        self.assertEqual(response.status_code, 200)

        self.designation.refresh_from_db()
        self.assertFalse(self.designation.is_active)
        self.assertIsNotNone(self.designation.deleted_at)
        self.assertEqual(DesignacionAutorizador.objects.count(), 1)  # fila conservada
        self.assertFalse(self.designation.scopes.filter(is_active=True).exists())
        self.assertFalse(puede_autorizar(self.target.id_usuario, "CN", self.clinica.id))
        self.assertTrue(AuditoriaEvento.objects.filter(accion="AuthorizerDesignationRevoked").exists())

        self.assertEqual(self.admin.get(f"{URL}{self.designation.id}/").status_code, 404)
        self.assertEqual(self.admin.delete(f"{URL}{self.designation.id}/").status_code, 404)

    def test_tras_la_baja_se_puede_crear_otra_designacion_del_mismo_par(self):
        self.admin.delete(f"{URL}{self.designation.id}/")
        response = self.admin.post(URL, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)


class LegacyAuthorizersEndpointTests(_Base):
    def test_s17_el_crud_antiguo_ya_no_existe(self):
        self.assertEqual(self.admin.get("/api/v1/authorizers/").status_code, 404)
        self.assertEqual(self.admin.get("/api/v1/authorizers/1/").status_code, 404)
