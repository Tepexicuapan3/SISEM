"""
Change auditoria-sync-expedientes: la actualizacion de un expediente desde
SERMED deja rastro de quien la pidio, del resultado y del antes/despues de la
replica; la consulta queda en bitacora_acceso; actualizar exige su propio
permiso.

La conexion 'expedientes' (replica) y Oracle no existen en tests: el
candado, la transaccion de la replica y sincronizar_tabla se simulan.
"""
import datetime as dt
from contextlib import nullcontext
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import (
    BitacoraAcceso,
    BitacoraReplicaSermed,
    BitacoraSyncExpediente,
    RelRolPermiso,
    RelUsuarioRol,
)
from apps.administracion.services import sync_service
from apps.administracion.services.sync_service import CambioReplica
from apps.administracion.use_cases.expedientes.actualizar_expediente import actualizar_expediente
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.catalogos.models import Permisos, Roles
from apps.consulta_medica.models import ChangeLog, Patient
from apps.consulta_medica.services import sermed_sync_service as sermed
from apps.consulta_medica.services.sermed_source import SermedEmployee

BASE = "apps.administracion.use_cases.expedientes.actualizar_expediente"
CONTEOS_VACIOS = {"insertados": 0, "eliminados": 0, "actualizados": 0}
LECTURA = "admin:gestion:expedientes:read"
ACTUALIZAR = "admin:gestion:expedientes:update"


def _usuario(login="operador"):
    user = SyUsuario.objects.create(
        usuario=login,
        correo=f"{login}@example.com",
        clave_hash=make_password("Password_123456"),
        est_activo=True,
        cambiar_clave=False,
        terminos_acept=True,
    )
    DetUsuario.objects.create(id_usuario=user, nombre="Op", paterno="Erador", materno="")
    return user


def _empleado(no_exp="100"):
    return SermedEmployee(
        no_exp=no_exp, paternal_surname="PEREZ", maternal_surname="GOMEZ", first_name="JUAN",
        birth_date=dt.date(1985, 3, 15), curp="PEGJ850315HDFRRN09", sex_code="M",
        valid_until=dt.date(2027, 1, 1), leave_date=None, leave_code=None, clinic_code="1",
    )


class _FuenteFalsa:
    def __init__(self, empleados=()):
        self._empleados = {e.no_exp: e for e in empleados}

    def employees(self, no_exps):
        return {n: self._empleados[n] for n in no_exps if n in self._empleados}

    def family_members(self, pk_nums):
        return {}


class _ReplicaSimulada:
    """Mixin: reemplaza Oracle, el candado y la transaccion de la replica."""

    candado_libre = True
    sincronizar = None

    def setUp(self):
        super().setUp()
        sincronizar = self.sincronizar or mock.Mock(return_value=dict(CONTEOS_VACIOS))
        self.sincronizar_mock = sincronizar
        parches = [
            mock.patch(f"{BASE}.obtener_conexion_oracle", return_value=mock.MagicMock()),
            mock.patch(f"{BASE}.sincronizar_tabla", sincronizar),
            mock.patch(f"{BASE}.candado_expediente", side_effect=lambda _e: nullcontext(self.candado_libre)),
            mock.patch(f"{BASE}._transaccion_replica", side_effect=nullcontext),
            mock.patch.object(sermed, "ReplicaSermedSource", return_value=_FuenteFalsa([_empleado()])),
        ]
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)


class ActualizarExpedienteBitacoraTests(_ReplicaSimulada, TestCase):
    def test_registra_quien_cuando_y_resultado_ok(self):
        user = _usuario()
        request = mock.Mock(META={"HTTP_USER_AGENT": "pruebas", "REMOTE_ADDR": "10.0.0.5"}, request_id="req-1")

        resultado = actualizar_expediente(
            "100", usuario=user, origen=BitacoraSyncExpediente.Origen.BOTON, request=request,
        )

        self.assertEqual(resultado["estado"], "OK")
        registro = BitacoraSyncExpediente.objects.get(pk=resultado["id_sync"])
        self.assertEqual(registro.usuario_id, user.pk)
        self.assertEqual(registro.cd_usuario, "operador")
        self.assertEqual(registro.origen, "BOTON")
        self.assertEqual(registro.no_exp, "100")
        self.assertEqual(registro.user_agent, "pruebas")
        self.assertEqual(registro.request_id, "req-1")
        self.assertEqual(registro.resultado, "OK")
        self.assertIsNotNone(registro.fecha_fin)
        self.assertEqual(registro.conteos["tablas"]["cat_empleados"], CONTEOS_VACIOS)
        self.assertIsNone(registro.errores)

    def test_sin_usuario_se_registra_como_proceso(self):
        resultado = actualizar_expediente("100")

        registro = BitacoraSyncExpediente.objects.get(pk=resultado["id_sync"])
        self.assertIsNone(registro.usuario_id)
        self.assertEqual(registro.cd_usuario, "SYNC_SERMED")
        self.assertEqual(registro.origen, "COMANDO")

    def test_el_usuario_real_queda_en_la_bitacora_de_cambios_del_paciente(self):
        user = _usuario()
        paciente = Patient.objects.create(no_exp="100", pk_num=0)

        actualizar_expediente("100", usuario=user, origen=BitacoraSyncExpediente.Origen.BOTON)

        cambio = ChangeLog.objects.get(table="cns_paciente", key=f"id_paciente|{paciente.pk}")
        self.assertEqual(cambio.user, str(user.pk))
        self.assertEqual(cambio.reason, ChangeLog.Reason.SERMED_SYNC)
        paciente.refresh_from_db()
        self.assertEqual(paciente.updated_by_id, user.pk)

    def test_cambios_de_la_replica_quedan_ligados_a_la_actualizacion(self):
        cambio = CambioReplica(
            "cat_empleados", "no_exp|100", "M",
            {"fec_vig": dt.date(2026, 1, 1)}, {"fec_vig": dt.date(2027, 1, 1)},
        )

        def sincronizar(**kwargs):
            if kwargs["tabla"] == "cat_empleados":
                kwargs["cambios"].append(cambio)
            return dict(CONTEOS_VACIOS)

        self.sincronizar_mock.side_effect = sincronizar
        resultado = actualizar_expediente("100")

        self.assertEqual(resultado["cambios_registrados"], 1)
        fila = BitacoraReplicaSermed.objects.get(sync_id=resultado["id_sync"])
        self.assertEqual(fila.tabla, "cat_empleados")
        self.assertEqual(fila.llave, "no_exp|100")
        self.assertEqual(fila.accion, "M")
        self.assertEqual(fila.valor_anterior, {"fec_vig": "2026-01-01"})
        self.assertEqual(fila.valor_nuevo, {"fec_vig": "2027-01-01"})

    def test_error_en_una_tabla_no_aplica_nada_ni_sincroniza_pacientes(self):
        self.sincronizar_mock.side_effect = RuntimeError("ORA-12541")

        with mock.patch.object(sermed, "sync_no_exp") as sync_pacientes:
            resultado = actualizar_expediente("100")

        self.assertEqual(resultado["estado"], "ERROR")
        sync_pacientes.assert_not_called()
        self.assertTrue(any("cat_empleados" in e and "ORA-12541" in e for e in resultado["errores"]))
        registro = BitacoraSyncExpediente.objects.get(pk=resultado["id_sync"])
        self.assertEqual(registro.resultado, "ERROR")
        self.assertFalse(BitacoraReplicaSermed.objects.exists())

    def test_falla_de_pacientes_es_parcial(self):
        with mock.patch.object(sermed, "sync_no_exp", side_effect=RuntimeError("sin red")):
            resultado = actualizar_expediente("100")

        self.assertEqual(resultado["estado"], "PARCIAL")
        registro = BitacoraSyncExpediente.objects.get(pk=resultado["id_sync"])
        self.assertEqual(registro.resultado, "PARCIAL")
        self.assertTrue(any("sin red" in e for e in registro.errores))


class ActualizarExpedienteOcupadoTests(_ReplicaSimulada, TestCase):
    candado_libre = False

    def test_otra_actualizacion_en_curso_no_toca_nada(self):
        resultado = actualizar_expediente("100")

        self.assertEqual(resultado["estado"], "OCUPADO")
        self.sincronizar_mock.assert_not_called()
        self.assertEqual(
            BitacoraSyncExpediente.objects.get(pk=resultado["id_sync"]).resultado, "OCUPADO",
        )


class BitacoraReplicaHelpersTests(TestCase):
    def test_fecha_oracle_a_medianoche_no_es_un_cambio(self):
        self.assertEqual(
            sync_service._comparable(dt.datetime(1985, 3, 15)),
            sync_service._comparable(dt.date(1985, 3, 15)),
        )
        self.assertNotEqual(
            sync_service._comparable(dt.datetime(2026, 1, 1, 10, 30)),
            sync_service._comparable(dt.date(2026, 1, 1)),
        )

    def test_los_binarios_se_guardan_como_hash(self):
        valor = sync_service._valor_bitacora(memoryview(b"foto"))
        self.assertEqual(set(valor), {"sha256", "bytes"})
        self.assertEqual(valor["bytes"], 4)
        self.assertEqual(valor, sync_service._valor_bitacora(b"foto"))

    def test_llave_legible_compuesta(self):
        self.assertEqual(
            sync_service._llave_legible(["id_empleado", "id_clave_foto"], (7, 2)),
            "id_empleado|7|id_clave_foto|2",
        )


class ExpedienteApiAuditoriaTests(APITestCase):
    def setUp(self):
        self.lectura = Permisos.objects.create(codigo=LECTURA, descripcion="Ver", is_active=True)
        # La migracion administracion 0015 ya lo da de alta.
        self.actualizar, _ = Permisos.objects.get_or_create(
            codigo=ACTUALIZAR, defaults={"descripcion": "Actualizar", "is_active": True},
        )
        self.user_lectura = self._usuario_con_permisos("solo_lectura", [self.lectura])
        self.user_actualiza = self._usuario_con_permisos("actualiza", [self.lectura, self.actualizar])

    def _usuario_con_permisos(self, login, permisos):
        rol = Roles.objects.create(
            rol=f"ROL_{login.upper()}", desc_rol=login, landing_route="/admin/expedientes", is_active=True,
        )
        for permiso in permisos:
            RelRolPermiso.objects.create(id_rol=rol, id_permiso=permiso)
        user = _usuario(login)
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=rol, is_primary=True)
        return user

    def _login(self, login):
        self.client.cookies.clear()
        PolicyStore().clear_active_session(SyUsuario.objects.get(usuario=login).id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": login, "password": "Password_123456"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies
        return response.cookies.get(CSRF_COOKIE).value

    def _post_actualizar(self, csrf, resultado):
        with mock.patch("apps.administracion.views.expediente_view.actualizar_expediente",
                        return_value=resultado) as caso:
            response = self.client.post(
                "/api/v1/expedientes/actualizar/", {"expediente": "40041"},
                format="json", HTTP_X_CSRF_TOKEN=csrf,
            )
        return response, caso

    def test_consultar_expediente_queda_en_bitacora_de_acceso_con_ultima_actualizacion(self):
        BitacoraSyncExpediente.objects.create(
            no_exp="40041", cd_usuario="actualiza", origen="BOTON", resultado="OK",
        )
        self._login("solo_lectura")

        with mock.patch("apps.administracion.views.expediente_view.buscar_expediente",
                        return_value={"empleados": [{"NO_EXP": "40041"}], "familiares": []}):
            response = self.client.get("/api/v1/expedientes/?id_empleado=40041")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ultima_actualizacion"]["usuario"], "actualiza")
        acceso = BitacoraAcceso.objects.get()
        self.assertEqual(acceso.accion, "ver")
        self.assertEqual(acceso.recurso, "expediente_sermed")
        self.assertEqual(acceso.no_exp, "40041")
        self.assertEqual(acceso.cd_usuario, "solo_lectura")

    def test_busqueda_por_nombre_queda_en_bitacora_de_acceso(self):
        self._login("solo_lectura")

        with mock.patch("apps.administracion.views.expediente_view.buscar_por_nombre", return_value=[]):
            response = self.client.get("/api/v1/expedientes/buscar-nombre/?nombre=Perez")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        acceso = BitacoraAcceso.objects.get()
        self.assertEqual(acceso.recurso, "expediente_sermed_busqueda")
        self.assertIsNone(acceso.no_exp)

    def test_solo_lectura_no_puede_actualizar(self):
        csrf = self._login("solo_lectura")

        response, caso = self._post_actualizar(csrf, {})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        caso.assert_not_called()

    def test_actualizar_pasa_el_usuario_y_el_origen_boton(self):
        csrf = self._login("actualiza")

        response, caso = self._post_actualizar(
            csrf, {"estado": "OK", "id_sync": 1, "tablas": {}, "errores": []},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        _, kwargs = caso.call_args
        self.assertEqual(kwargs["usuario"].usuario, "actualiza")
        self.assertEqual(kwargs["origen"], "BOTON")

    def test_ocupado_responde_409(self):
        csrf = self._login("actualiza")

        response, _ = self._post_actualizar(
            csrf, {"estado": "OCUPADO", "id_sync": 2, "tablas": {}, "errores": ["ya se actualiza"]},
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "SYNC_EN_CURSO")

    def test_error_responde_502_con_detalle(self):
        csrf = self._login("actualiza")

        response, _ = self._post_actualizar(
            csrf, {"estado": "ERROR", "id_sync": 3, "tablas": {}, "errores": ["Error en tabla cat_empleados"]},
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["code"], "SYNC_ERROR")
        self.assertEqual(response.data["details"]["id_sync"], 3)
