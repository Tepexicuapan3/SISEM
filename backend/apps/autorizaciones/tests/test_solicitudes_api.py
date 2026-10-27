"""API de solicitudes (F3): bandeja, detalle (destino del boton), decision.

El enlace de la notificacion solo navega: el GET nunca cambia el estado.
Decidir exige sesion, CSRF, permiso, politica vigente, version y firma.
"""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento, RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.autorizaciones.contracts import solicitar_autorizacion
from apps.autorizaciones.models import SolicitudDestinatario
from apps.catalogos.models import CatPermiso, CatRol

from .fabricas import agregar_alcance, asignar_tipo, crear_autorizador, crear_centro, crear_usuario, motivo

URL = "/api/v1/autorizaciones/solicitudes/"
CLAVE = "Clave_12345"
LEER = "clinico:autorizaciones:read"
DECIDIR = "clinico:autorizaciones:decide"


def _cliente(usuario, permisos, *, con_csrf=True):
    from rest_framework.test import APIClient

    rol = CatRol.objects.create(
        rol=f"ROL_{usuario.usuario}", desc_rol="rol de prueba", landing_route="/", is_active=True,
    )
    for codigo in permisos:
        permiso, _ = CatPermiso.objects.get_or_create(codigo=codigo, defaults={"descripcion": codigo, "is_active": True})
        RelRolPermiso.objects.create(id_rol=rol, id_permiso=permiso)
    RelUsuarioRol.objects.create(id_usuario=usuario, id_rol=rol, is_primary=True)
    PolicyStore().clear_active_session(usuario.id_usuario)
    cliente = APIClient()
    respuesta = cliente.post("/api/v1/auth/login", {"username": usuario.usuario, "password": CLAVE}, format="json")
    assert respuesta.status_code == status.HTTP_200_OK, respuesta.content
    cliente.cookies = respuesta.cookies
    if con_csrf:
        cliente.defaults["HTTP_X_CSRF_TOKEN"] = respuesta.cookies.get(CSRF_COOKIE).value
    return cliente


class _Base(APITestCase):
    def setUp(self):
        cache.clear()
        hoy = timezone.localdate()
        self.centro = crear_centro()
        self.otro_centro = crear_centro()
        self.medico = crear_usuario()

        self.autorizador = crear_autorizador(inicio=hoy - timedelta(days=10), fin=hoy + timedelta(days=200))
        agregar_alcance(asignar_tipo(self.autorizador, "REC"), "CENTRO", self.centro)
        self.cliente = _cliente(self.autorizador.usuario, [LEER, DECIDIR])

        self.ajeno = crear_autorizador(inicio=hoy - timedelta(days=10), fin=hoy + timedelta(days=200))
        agregar_alcance(asignar_tipo(self.ajeno, "REC"), "CENTRO", self.otro_centro)
        self.cliente_ajeno = _cliente(self.ajeno.usuario, [LEER, DECIDIR])

        self.solicitud = solicitar_autorizacion(
            clave_tipo="REC", id_origen=77, folio_origen="RX-2026-000077", id_centro=self.centro.id,
            id_usuario_solicitante=self.medico.id_usuario,
            items=[{"tipoItem": "MEDICAMENTO", "idItemOrigen": 1, "descripcion": "Metilfenidato 10 mg",
                    "cantidad": 30, "motivo": "MEDICAMENTO_CONTROLADO"}],
            motivos=["MEDICAMENTO_CONTROLADO"],
            resumen_minimo={"medicamentos": 1},
            id_paciente=4242,
        )
        self.detalle = f"{URL}{self.solicitud.uuid_publico}/"


class BandejaTests(_Base):
    def test_lista_solo_lo_que_el_autorizador_puede_gestionar(self):
        respuesta = self.cliente.get(URL, {"estatus": "PENDIENTE"})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        self.assertEqual([s["folio"] for s in respuesta.json()["items"]], [self.solicitud.folio])
        self.assertEqual(self.cliente_ajeno.get(URL).json()["items"], [])

    def test_bandeja_exige_permiso(self):
        sin_permiso = _cliente(crear_usuario(), [])
        self.assertEqual(sin_permiso.get(URL).status_code, status.HTTP_403_FORBIDDEN)

    def test_filtros(self):
        self.assertEqual(self.cliente.get(URL, {"estatus": "AUTORIZADA"}).json()["items"], [])
        self.assertEqual(len(self.cliente.get(URL, {"tipo": "REC", "folio": self.solicitud.folio}).json()["items"]), 1)
        self.assertEqual(self.cliente.get(URL, {"estatus": "NO_EXISTE"}).status_code, status.HTTP_400_BAD_REQUEST)


class DetalleTests(_Base):
    def test_detalle_no_cambia_la_solicitud_y_marca_visto(self):
        respuesta = self.cliente.get(self.detalle)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        cuerpo = respuesta.json()["solicitud"]
        self.assertEqual(cuerpo["estatus"], "PENDIENTE")
        self.assertEqual(cuerpo["acciones"], {
            "puedeAprobar": True, "puedeRechazar": True, "motivoBloqueo": None, "mensajeBloqueo": None,
        })
        self.assertEqual(cuerpo["items"][0]["descripcion"], "Metilfenidato 10 mg")
        self.assertEqual(
            SolicitudDestinatario.objects.get(solicitud=self.solicitud, autorizador=self.autorizador).estatus, "VISTO",
        )

    def test_lectura_queda_en_la_bitacora(self):
        self.cliente.get(self.detalle)
        self.assertTrue(AuditoriaEvento.objects.filter(accion="SolicitudConsultada", recurso_tipo="solicitud_autorizacion").exists())

    def test_no_expone_identidad_del_paciente(self):
        cuerpo = self.cliente.get(self.detalle).json()["solicitud"]
        self.assertNotIn("idPaciente", cuerpo)
        self.assertNotIn("4242", str(cuerpo))

    def test_quien_no_cubre_el_centro_no_la_encuentra(self):
        self.assertEqual(self.cliente_ajeno.get(self.detalle).status_code, status.HTTP_404_NOT_FOUND)

    def test_suspendido_ve_el_motivo_de_bloqueo(self):
        from apps.autorizaciones.models import Autorizador

        Autorizador.objects.filter(pk=self.autorizador.pk).update(
            estatus="SUSPENDIDO", motivo_estatus=motivo("SUSPENSION", "LICENCIA"),
        )
        acciones = self.cliente.get(self.detalle).json()["solicitud"]["acciones"]
        self.assertFalse(acciones["puedeAprobar"])
        self.assertEqual(acciones["motivoBloqueo"], "AUTORIZADOR_SUSPENDIDO")
        self.assertIn("suspendido", acciones["mensajeBloqueo"].lower())


class DecisionTests(_Base):
    def decidir(self, cliente=None, **cambios):
        datos = {"decision": "APROBAR", "version": self.solicitud.version, "credencial": CLAVE}
        datos.update(cambios)
        return (cliente or self.cliente).post(f"{self.detalle}decision/", datos, format="json")

    def test_autorizar_desde_el_detalle(self):
        respuesta = self.decidir()
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        self.assertEqual(respuesta.json()["solicitud"]["estatus"], "AUTORIZADA")
        self.assertTrue(AuditoriaEvento.objects.filter(accion="SolicitudAutorizada").exists())

    def test_sin_csrf(self):
        sin_csrf = _cliente(crear_autorizador().usuario, [LEER, DECIDIR], con_csrf=False)
        respuesta = self.decidir(cliente=sin_csrf)
        self.assertEqual(respuesta.json()["code"], "CSRF_INVALID")

    def test_sin_permiso_de_decidir(self):
        hoy = timezone.localdate()
        solo_lectura = crear_autorizador(inicio=hoy - timedelta(days=1), fin=hoy + timedelta(days=10))
        agregar_alcance(asignar_tipo(solo_lectura, "REC"), "CENTRO", self.centro)
        respuesta = self.decidir(cliente=_cliente(solo_lectura.usuario, [LEER]))
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_firma(self):
        respuesta = self.decidir(credencial="")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(respuesta.json()["code"], "REAUTH_FAILED")

    def test_version_vieja(self):
        respuesta = self.decidir(version=self.solicitud.version + 3)
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.json()["code"], "STALE_VERSION")

    def test_rechazo_con_motivo(self):
        respuesta = self.decidir(decision="RECHAZAR", motivoId=motivo("RECHAZO", "NO_JUSTIFICADO").id_motivo)
        self.assertEqual(respuesta.json()["solicitud"]["estatus"], "RECHAZADA")


class MotivosRechazoTests(_Base):
    def test_el_autorizador_clinico_obtiene_los_motivos_de_rechazo(self):
        respuesta = self.cliente.get("/api/v1/autorizaciones/motivos-rechazo/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        motivos = respuesta.json()["items"]
        self.assertIn("NO_JUSTIFICADO", {m["clave"] for m in motivos})
        otro = next(m for m in motivos if m["clave"] == "OTRO")
        self.assertTrue(otro["requiereDescripcionLibre"])

    def test_exige_permiso_de_lectura_clinico(self):
        sin_permiso = _cliente(crear_usuario(), [])
        self.assertEqual(
            sin_permiso.get("/api/v1/autorizaciones/motivos-rechazo/").status_code, status.HTTP_403_FORBIDDEN,
        )
