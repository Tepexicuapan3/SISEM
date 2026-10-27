"""API /api/v1/autorizadores/ (F1): permisos, CSRF, contrato, filtros y auditoria."""
from datetime import date, timedelta

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.autorizaciones.models import AutorizadorMovimiento
from apps.catalogos.models import CatPermiso, CatRol

from .fabricas import crear_centro, crear_usuario, motivo

URL = "/api/v1/autorizadores/"
CLAVE = "Admin_123456"
LECTURA = "admin:autorizadores:read"
ALTA = "admin:autorizadores:create"
EDICION = "admin:autorizadores:update"
ESTATUS = "admin:autorizadores:status"


def _cliente(usuario_login, permisos, *, con_csrf=True):
    rol = CatRol.objects.create(
        rol=f"ROL_{usuario_login}", desc_rol="rol de prueba", landing_route="/admin", is_active=True,
    )
    for codigo in permisos:
        permiso, _ = CatPermiso.objects.get_or_create(
            codigo=codigo, defaults={"descripcion": codigo, "is_active": True},
        )
        RelRolPermiso.objects.create(id_rol=rol, id_permiso=permiso)
    usuario = SyUsuario.objects.create(
        usuario=usuario_login,
        correo=f"{usuario_login}@example.com",
        clave_hash=make_password(CLAVE),
        est_activo=True,
        cambiar_clave=False,
        terminos_acept=True,
    )
    DetUsuario.objects.create(id_usuario=usuario, nombre="Admin", paterno=usuario_login, materno="")
    RelUsuarioRol.objects.create(id_usuario=usuario, id_rol=rol, is_primary=True)
    PolicyStore().clear_active_session(usuario.id_usuario)

    cliente = APIClient()
    respuesta = cliente.post(
        "/api/v1/auth/login", {"username": usuario_login, "password": CLAVE}, format="json",
    )
    assert respuesta.status_code == status.HTTP_200_OK, respuesta.content
    cliente.cookies = respuesta.cookies
    if con_csrf:
        cliente.defaults["HTTP_X_CSRF_TOKEN"] = respuesta.cookies.get(CSRF_COOKIE).value
    return cliente, usuario


class _Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin, self.admin_usuario = _cliente("adm_aut", [LECTURA, ALTA, EDICION, ESTATUS])
        self.medico = crear_usuario()
        self.centro = crear_centro()

    def cuerpo(self, usuario=None, **cambios):
        datos = {
            "usuarioId": (usuario or self.medico).id_usuario,
            "cargo": "Jefe de servicio",
            "numeroOficio": "OF-1",
            "fechaInicioVigencia": "2026-01-01",
            "fechaFinVigencia": "2026-12-31",
            "tipos": [{"claveTipo": "REC", "alcance": {"centros": [self.centro.id]}}],
        }
        datos.update(cambios)
        return datos

    def crear(self, usuario=None, **cambios):
        respuesta = self.admin.post(URL, self.cuerpo(usuario, **cambios), format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.content)
        return respuesta.json()["autorizador"]


class PermisosTests(_Base):
    def test_listar_sin_permiso_de_lectura(self):
        cliente, _ = _cliente("sin_permiso", [])
        self.assertEqual(cliente.get(URL).status_code, status.HTTP_403_FORBIDDEN)

    def test_alta_exige_permiso_de_alta(self):
        cliente, _ = _cliente("solo_lectura", [LECTURA])
        respuesta = cliente.post(URL, self.cuerpo(), format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(respuesta.json()["code"], "INSUFFICIENT_PERMISSIONS")

    def test_cambiar_estatus_exige_permiso_de_estatus(self):
        creado = self.crear()
        cliente, _ = _cliente("editor", [LECTURA, EDICION])
        respuesta = cliente.post(
            f"{URL}{creado['id']}/suspender/",
            {"motivoId": motivo("SUSPENSION", "LICENCIA").id_motivo, "version": creado["version"]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_mutacion_sin_csrf(self):
        cliente, _ = _cliente("sin_csrf", [LECTURA, ALTA], con_csrf=False)
        respuesta = cliente.post(URL, self.cuerpo(), format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(respuesta.json()["code"], "CSRF_INVALID")


class ContratoTests(_Base):
    def test_alta_devuelve_el_registro_completo_en_camel_case(self):
        creado = self.crear()

        self.assertEqual(creado["usuario"]["id"], self.medico.id_usuario)
        self.assertTrue(creado["usuario"]["nombreCompleto"])
        self.assertEqual(creado["usuario"]["cedulas"][0]["esPrincipal"], True)
        self.assertEqual(creado["estatus"], "ACTIVO")
        self.assertIn(creado["estadoVigencia"], ("VIGENTE", "POR_VENCER", "VENCIDO", "PENDIENTE_INICIO"))
        self.assertEqual(creado["fechaFinVigencia"], "2026-12-31")
        self.assertEqual(creado["tipos"][0]["clave"], "REC")
        self.assertEqual(creado["tipos"][0]["alcance"]["centros"][0]["id"], self.centro.id)
        self.assertEqual(creado["creadoPor"]["id"], self.admin_usuario.id_usuario)
        self.assertIn("fechaCreacion", creado)
        self.assertEqual(creado["version"], 1)

    def test_alta_queda_auditada(self):
        creado = self.crear()
        evento = AuditoriaEvento.objects.get(accion="AutorizadorCreado")
        self.assertEqual(evento.recurso_tipo, "autorizador")
        self.assertEqual(str(evento.recurso_id), str(creado["id"]))
        self.assertIsNone(evento.datos_antes)
        self.assertEqual(evento.datos_despues["usuarioId"], self.medico.id_usuario)

    def test_error_de_negocio_con_contrato_estandar(self):
        self.crear()
        respuesta = self.admin.post(URL, self.cuerpo(), format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["code"], "AUTHORIZER_EXISTS")
        for campo in ("message", "status", "details", "timestamp"):
            self.assertIn(campo, cuerpo)

    def test_detalle_y_edicion_con_version(self):
        creado = self.crear()
        detalle = self.admin.get(f"{URL}{creado['id']}/")
        self.assertEqual(detalle.status_code, status.HTTP_200_OK)

        respuesta = self.admin.patch(f"{URL}{creado['id']}/", {
            "cargo": "Subdirector",
            "numeroOficio": "OF-2",
            "tipos": creado_a_tipos(creado),
            "version": creado["version"],
        }, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        self.assertEqual(respuesta.json()["autorizador"]["cargo"], "Subdirector")
        self.assertEqual(respuesta.json()["autorizador"]["version"], 2)

        repetida = self.admin.patch(f"{URL}{creado['id']}/", {
            "cargo": "Otro", "tipos": creado_a_tipos(creado), "version": creado["version"],
        }, format="json")
        self.assertEqual(repetida.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(repetida.json()["code"], "STALE_VERSION")

    def test_suspender_reactivar_renovar_baja_e_historial(self):
        creado = self.crear()
        base = f"{URL}{creado['id']}/"

        r = self.admin.post(f"{base}suspender/", {
            "motivoId": motivo("SUSPENSION", "LICENCIA").id_motivo, "version": 1,
        }, format="json")
        self.assertEqual(r.json()["autorizador"]["estatus"], "SUSPENDIDO")
        r = self.admin.post(f"{base}reactivar/", {"version": 2}, format="json")
        self.assertEqual(r.json()["autorizador"]["estatus"], "ACTIVO")
        r = self.admin.post(f"{base}renovar/", {"fechaFinVigencia": "2027-12-31", "version": 3}, format="json")
        self.assertEqual(r.json()["autorizador"]["fechaFinVigencia"], "2027-12-31")
        r = self.admin.post(f"{base}baja/", {
            "motivoId": motivo("BAJA", "BAJA_LABORAL").id_motivo, "version": 4,
        }, format="json")
        self.assertEqual(r.json()["autorizador"]["estatus"], "INACTIVO")

        historial = self.admin.get(f"{base}historial/").json()["items"]
        self.assertEqual(
            [m["tipoMovimiento"] for m in historial],
            ["BAJA", "RENOVACION", "REACTIVACION", "SUSPENSION", "ALTA"],
        )
        self.assertEqual(historial[0]["motivo"]["clave"], "BAJA_LABORAL")
        self.assertEqual(historial[0]["responsable"]["id"], self.admin_usuario.id_usuario)
        self.assertEqual(AutorizadorMovimiento.objects.filter(autorizador_id=creado["id"]).count(), 5)


def creado_a_tipos(creado):
    return [
        {
            "claveTipo": t["clave"],
            "alcance": {
                "centros": [c["id"] for c in t["alcance"]["centros"]],
                "tiposCentro": t["alcance"]["tiposCentro"],
                "global": t["alcance"]["global"],
            },
        }
        for t in creado["tipos"]
    ]


class FiltrosTests(_Base):
    def setUp(self):
        super().setUp()
        hoy = date.today()
        self.vigente = self.crear(
            fechaInicioVigencia=str(hoy - timedelta(days=30)),
            fechaFinVigencia=str(hoy + timedelta(days=200)),
        )
        hospital = crear_centro("HOSPITAL")
        self.por_vencer = self.crear(
            crear_usuario(),
            fechaInicioVigencia=str(hoy - timedelta(days=30)),
            fechaFinVigencia=str(hoy + timedelta(days=5)),
            tipos=[{"claveTipo": "LAB", "alcance": {"centros": [hospital.id]}}],
        )
        self.hospital = hospital

    def ids(self, **params):
        respuesta = self.admin.get(URL, params)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        return {item["id"] for item in respuesta.json()["items"]}

    def test_sin_filtros_lista_todos(self):
        self.assertEqual(self.ids(), {self.vigente["id"], self.por_vencer["id"]})

    def test_por_tipo_centro_estatus_y_vigencia(self):
        self.assertEqual(self.ids(tipo="LAB"), {self.por_vencer["id"]})
        self.assertEqual(self.ids(centroId=self.hospital.id), {self.por_vencer["id"]})
        self.assertEqual(self.ids(estatus="ACTIVO"), {self.vigente["id"], self.por_vencer["id"]})
        self.assertEqual(self.ids(vigencia="POR_VENCER"), {self.por_vencer["id"]})
        self.assertEqual(self.ids(vigencia="VIGENTE"), {self.vigente["id"]})

    def test_por_nombre_o_usuario(self):
        self.assertEqual(self.ids(search=self.medico.usuario), {self.vigente["id"]})

    def test_filtros_combinados(self):
        self.assertEqual(self.ids(tipo="REC", vigencia="POR_VENCER"), set())

    def test_filtro_invalido(self):
        respuesta = self.admin.get(URL, {"vigencia": "CASI"})
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)


class UsuariosElegiblesTests(_Base):
    def test_excluye_inactivos_y_a_quien_ya_es_autorizador(self):
        self.crear()
        inactivo = crear_usuario()
        inactivo.est_activo = False
        inactivo.save()
        disponible = crear_usuario()

        respuesta = self.admin.get(f"{URL}usuarios-elegibles/", {"search": "autorizador_"})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        ids = {u["id"] for u in respuesta.json()["items"]}
        self.assertIn(disponible.id_usuario, ids)
        self.assertNotIn(self.medico.id_usuario, ids)
        self.assertNotIn(inactivo.id_usuario, ids)
        elegido = next(u for u in respuesta.json()["items"] if u["id"] == disponible.id_usuario)
        self.assertTrue(elegido["tieneCedula"])


class CatalogosTests(_Base):
    def test_tipos_y_motivos_para_la_pantalla(self):
        respuesta = self.admin.get("/api/v1/autorizaciones/catalogos/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        cuerpo = respuesta.json()
        self.assertEqual({t["clave"] for t in cuerpo["tipos"]}, {"LAB", "GAB", "REC", "CNO"})
        self.assertIn("SUSPENSION", {m["ambito"] for m in cuerpo["motivos"]})
