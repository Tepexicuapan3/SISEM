"""GET /api/v1/medicos/legado: archivo legado de solo lectura. Un código legado
(`no_medico`) jamás se resuelve como `CatMedico.id`."""

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import Permisos, Roles
from apps.medicos.models import LegacyMedico
from apps.medicos.tests.factories import crear_medico

URL = "/api/v1/medicos/legado"


class LegacyMedicosApiTests(APITestCase):
    def setUp(self):
        role, _ = Roles.objects.get_or_create(
            rol="ADMIN_MEDICOS_LEGADO_TEST",
            defaults={"desc_rol": "Admin medicos legado (test)", "landing_route": "/admin"},
        )
        permiso, _ = Permisos.objects.get_or_create(
            codigo="admin:gestion:medicos:read",
            defaults={"descripcion": "Leer medicos", "is_active": True},
        )
        RelRolPermiso.objects.get_or_create(id_rol=role, id_permiso=permiso)
        user = SyUsuario.objects.create(
            usuario="admin_legado", correo="admin_legado@example.com",
            clave_hash=make_password("x"), est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=user, nombre="Admin", paterno="Legado")
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=role, is_primary=True)
        self.user = user
        access, _r, _s = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.auth_cookie = access

    def _login(self):
        self.client.cookies["access_token_cookie"] = self.auth_cookie

    def _get(self, **params):
        self._login()
        return self.client.get(URL, params)

    def _mk(self, no, **kw):
        kw.setdefault("cd_medico", f"C{no}")
        kw.setdefault("sw_status", "A")
        return LegacyMedico.objects.create(no_medico=no, **kw)

    def test_requiere_autenticacion(self):
        resp = self.client.get(URL)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_solo_lectura(self):
        self._login()
        self.assertEqual(self.client.post(URL, {}, format="json").status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(URL).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_contrato_item_y_nombre_completo(self):
        self._mk(
            7, ds_nombre="JUAN", ds_paterno="PEREZ", ds_materno=None, no_cedula="123",
            cd_sexo="M", cd_clinica=3, ds_clinica="CLINICA 3", cd_especialidad=9,
            ds_especialidad="CARDIO", cd_usuario="jperez",
        )
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total"], 1)
        item = resp.data["items"][0]
        self.assertEqual(item["noMedico"], 7)
        self.assertEqual(item["claveRh"], "C7")
        self.assertEqual(item["nombreCompleto"], "JUAN PEREZ")
        self.assertEqual(item["cedula"], "123")
        self.assertEqual(item["clinica"], {"clave": 3, "descripcion": "CLINICA 3"})
        self.assertEqual(item["especialidad"], {"clave": 9, "descripcion": "CARDIO"})
        self.assertEqual(item["estatus"], "A")
        self.assertEqual(item["usuarioLegado"], "jperez")
        self.assertIsNone(item["medicoActual"])
        self.assertNotIn("feNac", item)

    def test_busqueda_por_tokens_de_nombre(self):
        self._mk(1, ds_nombre="MARIA", ds_paterno="LOPEZ", ds_materno="RUIZ")
        self._mk(2, ds_nombre="MARIA", ds_paterno="GOMEZ", ds_materno="RUIZ")
        resp = self._get(search="maria lopez")
        self.assertEqual([i["noMedico"] for i in resp.data["items"]], [1])
        resp = self._get(search="ruiz")
        self.assertEqual(resp.data["total"], 2)

    def test_busqueda_por_cedula_y_clave_rh(self):
        self._mk(1, no_cedula="ABC9988", cd_medico="0512")
        self._mk(2, no_cedula="ZZZ", cd_medico="0777")
        self.assertEqual([i["noMedico"] for i in self._get(search="9988").data["items"]], [1])
        self.assertEqual([i["noMedico"] for i in self._get(search="0777").data["items"]], [2])

    def test_token_numerico_busca_no_medico_exacto(self):
        self._mk(55, cd_medico="X1")
        self._mk(555, cd_medico="X2")
        resp = self._get(search="55")
        self.assertEqual([i["noMedico"] for i in resp.data["items"]], [55])

    def test_filtro_status(self):
        self._mk(1, sw_status="A")
        self._mk(2, sw_status="B")
        resp = self._get(status="B")
        self.assertEqual([i["noMedico"] for i in resp.data["items"]], [2])

    def test_paginacion_y_orden(self):
        for n, pat in enumerate(["D", "A", "C", "B", "E"], start=1):
            self._mk(n, ds_paterno=pat)
        resp = self._get(page=2, pageSize=2)
        self.assertEqual(resp.data["total"], 5)
        self.assertEqual(resp.data["page"], 2)
        self.assertEqual(resp.data["pageSize"], 2)
        self.assertEqual(resp.data["totalPages"], 3)
        self.assertEqual([i["paterno"] for i in resp.data["items"]], ["C", "D"])

    def test_page_invalido_400(self):
        self.assertEqual(self._get(page="x").status_code, 400)

    def test_medico_actual_presente_y_ausente(self):
        medico = crear_medico(nombre="Ana", paterno="Torres")
        self._mk(1, medico_actual=medico)
        self._mk(2)
        items = {i["noMedico"]: i for i in self._get().data["items"]}
        self.assertEqual(items[1]["medicoActual"]["id"], medico.id)
        self.assertEqual(items[1]["medicoActual"]["nombreCompleto"], "Ana Torres")
        self.assertIsNone(items[2]["medicoActual"])

    def test_sin_n_mas_1(self):
        def poblar(n):
            LegacyMedico.objects.all().delete()
            for i in range(n):
                self._mk(100 + i, medico_actual=crear_medico(nombre=f"M{i}"))

        self._login()
        poblar(1)
        with self.assertNumQueries(self._contar()):
            self.client.get(URL)
        poblar(5)
        with self.assertNumQueries(self._contar()):
            self.client.get(URL)

    def _contar(self):
        # Mide la cantidad de queries con 1 fila y exige el mismo número con 5.
        if not hasattr(self, "_n_queries"):
            from django.db import connection
            from django.test.utils import CaptureQueriesContext

            self._login()
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(URL)
            self._n_queries = len(ctx)
        return self._n_queries

    def test_no_medico_igual_a_id_de_catmedico_no_se_resuelve(self):
        # Regla de oro: el código legado 1 NO es el médico SIRES con id 1.
        otro = crear_medico(id=1, nombre="Otro", paterno="Medico")
        self._mk(1, ds_nombre="LEGADO", ds_paterno="UNO")
        item = self._get().data["items"][0]
        self.assertEqual(item["noMedico"], 1)
        self.assertIsNone(item["medicoActual"])
        self.assertNotIn(otro.id_usuario.usuario, str(item))
