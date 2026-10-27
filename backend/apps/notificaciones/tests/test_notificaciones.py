"""Modulo tecnico de notificaciones (F4): bandeja interna, tiempo real y correo.

Registra a quien se envio, cuando y el resultado de cada canal.
"""
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.token_service import CSRF_COOKIE
from apps.notificaciones.models import Entrega, Notificacion
from apps.notificaciones.services import notificacion_service as servicio
from apps.notificaciones.tasks import enviar_correo_notificacion

CLAVE = "Clave_12345"
_n = {"n": 0}


def _usuario(correo=True):
    _n["n"] += 1
    n = _n["n"]
    usuario = SyUsuario.objects.create(
        usuario=f"ntf_{n}", correo=f"ntf_{n}@example.com" if correo else "",
        clave_hash=make_password(CLAVE), est_activo=True, cambiar_clave=False, terminos_acept=True,
    )
    DetUsuario.objects.create(id_usuario=usuario, nombre="Ana", paterno=f"Prueba{n}", materno="")
    return usuario


def _notificar(usuarios, **extra):
    datos = {
        "categoria": "AUT_SOLICITADA",
        "titulo": "Solicitud de autorización pendiente",
        "cuerpo": "AUT-2026-000001 · Recetas · Clínica 1",
        "tipo_recurso": "solicitud_autorizacion",
        "referencia_recurso": "6f1c",
        "url_accion": "/autorizaciones/solicitudes/6f1c",
    }
    datos.update(extra)
    return servicio.notificar([u.id_usuario for u in usuarios], **datos)


class ServicioTests(TestCase):
    def test_crea_una_notificacion_por_usuario_con_sus_canales(self):
        a, b = _usuario(), _usuario()
        with mock.patch.object(servicio, "_publicar_tiempo_real"), mock.patch.object(servicio, "_encolar_correo"):
            notificaciones = _notificar([a, b])

        self.assertEqual(len(notificaciones), 2)
        entrega = Entrega.objects.filter(notificacion=notificaciones[0])
        self.assertEqual(
            dict(entrega.values_list("canal", "estatus")),
            {"INTERNA": "ENVIADA", "TIEMPO_REAL": "PENDIENTE", "CORREO": "PENDIENTE"},
        )
        self.assertIn("***", entrega.get(canal="CORREO").destino_enmascarado)

    def test_sin_correo_registrado_el_canal_se_omite(self):
        sin_correo = _usuario(correo=False)
        with mock.patch.object(servicio, "_publicar_tiempo_real"), mock.patch.object(servicio, "_encolar_correo"):
            notificacion = _notificar([sin_correo])[0]
        self.assertEqual(Entrega.objects.get(notificacion=notificacion, canal="CORREO").estatus, "OMITIDA")

    def test_usuarios_repetidos_o_inexistentes(self):
        a = _usuario()
        with mock.patch.object(servicio, "_publicar_tiempo_real"), mock.patch.object(servicio, "_encolar_correo"):
            notificaciones = servicio.notificar(
                [a.id_usuario, a.id_usuario, 999999], categoria="X", titulo="t", cuerpo="c",
                tipo_recurso="r", referencia_recurso="1", url_accion="/x",
            )
        self.assertEqual(len(notificaciones), 1)

    def test_tiempo_real_y_correo_salen_despues_del_commit(self):
        a = _usuario()
        with mock.patch("apps.notificaciones.services.notificacion_service.RealtimePublisher") as publicador, \
                mock.patch("apps.notificaciones.tasks.enviar_correo_notificacion.delay") as correo, \
                self.captureOnCommitCallbacks(execute=True):
            notificacion = _notificar([a])[0]

        llamada = publicador.return_value.publish.call_args.kwargs
        self.assertEqual(llamada["group_names"], [f"user.{a.id_usuario}"])
        self.assertEqual(llamada["event_type"], "notification.created")
        self.assertEqual(llamada["payload"]["urlAccion"], "/autorizaciones/solicitudes/6f1c")
        self.assertEqual(Entrega.objects.get(notificacion=notificacion, canal="TIEMPO_REAL").estatus, "ENVIADA")
        correo.assert_called_once_with(notificacion.pk)

    def test_falla_de_tiempo_real_queda_registrada_y_no_rompe(self):
        a = _usuario()
        with mock.patch("apps.notificaciones.services.notificacion_service.RealtimePublisher") as publicador, \
                mock.patch("apps.notificaciones.tasks.enviar_correo_notificacion.delay"), \
                self.captureOnCommitCallbacks(execute=True):
            publicador.return_value.publish.side_effect = RuntimeError("redis caido")
            notificacion = _notificar([a])[0]
        entrega = Entrega.objects.get(notificacion=notificacion, canal="TIEMPO_REAL")
        self.assertEqual(entrega.estatus, "FALLIDA")
        self.assertIn("redis caido", entrega.detalle_error)

    def test_tarea_de_correo_registra_resultado(self):
        a = _usuario()
        with mock.patch.object(servicio, "_publicar_tiempo_real"), mock.patch.object(servicio, "_encolar_correo"):
            notificacion = _notificar([a])[0]

        with mock.patch("apps.notificaciones.tasks.send_notification_email_batch",
                        return_value={"sent": 1, "failed": []}) as enviar:
            enviar_correo_notificacion(notificacion.pk)
        self.assertEqual(Entrega.objects.get(notificacion=notificacion, canal="CORREO").estatus, "ENVIADA")
        mensaje = enviar.call_args.args[2]
        self.assertIn("AUT-2026-000001", mensaje)
        self.assertIn("/autorizaciones/solicitudes/6f1c", mensaje)

        with mock.patch("apps.notificaciones.tasks.send_notification_email_batch",
                        return_value={"sent": 0, "failed": [{"email": "x"}]}):
            enviar_correo_notificacion(notificacion.pk)
        entrega = Entrega.objects.get(notificacion=notificacion, canal="CORREO")
        self.assertEqual((entrega.estatus, entrega.intentos), ("FALLIDA", 2))


class ApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.usuario = _usuario()
        self.otro = _usuario()
        with mock.patch.object(servicio, "_publicar_tiempo_real"), mock.patch.object(servicio, "_encolar_correo"):
            self.mia = _notificar([self.usuario])[0]
            _notificar([self.usuario], titulo="Segunda")
            self.ajena = _notificar([self.otro])[0]
        self.cliente = self._cliente(self.usuario)

    def _cliente(self, usuario, con_csrf=True):
        PolicyStore().clear_active_session(usuario.id_usuario)
        cliente = APIClient()
        respuesta = cliente.post("/api/v1/auth/login", {"username": usuario.usuario, "password": CLAVE}, format="json")
        assert respuesta.status_code == 200, respuesta.content
        cliente.cookies = respuesta.cookies
        if con_csrf:
            cliente.defaults["HTTP_X_CSRF_TOKEN"] = respuesta.cookies.get(CSRF_COOKIE).value
        return cliente

    def test_solo_ve_las_suyas(self):
        respuesta = self.cliente.get("/api/v1/notificaciones/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        ids = {n["id"] for n in respuesta.json()["items"]}
        self.assertIn(self.mia.pk, ids)
        self.assertNotIn(self.ajena.pk, ids)

    def test_contador_y_marcar_leida(self):
        self.assertEqual(self.cliente.get("/api/v1/notificaciones/contador/").json()["noLeidas"], 2)
        respuesta = self.cliente.patch(f"/api/v1/notificaciones/{self.mia.pk}/leida/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(respuesta.json()["notificacion"]["fechaLectura"])
        self.assertEqual(self.cliente.get("/api/v1/notificaciones/contador/").json()["noLeidas"], 1)
        solo = self.cliente.get("/api/v1/notificaciones/", {"soloNoLeidas": "true"}).json()["items"]
        self.assertEqual(len(solo), 1)

    def test_no_puede_marcar_las_de_otro(self):
        respuesta = self.cliente.patch(f"/api/v1/notificaciones/{self.ajena.pk}/leida/")
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)

    def test_marcar_todas(self):
        respuesta = self.cliente.post("/api/v1/notificaciones/marcar-todas-leidas/")
        self.assertEqual(respuesta.json()["actualizadas"], 2)
        self.assertEqual(self.cliente.get("/api/v1/notificaciones/contador/").json()["noLeidas"], 0)

    def test_sin_sesion_y_sin_csrf(self):
        self.assertIn(APIClient().get("/api/v1/notificaciones/").status_code, (401, 403))
        sin_csrf = self._cliente(self.otro, con_csrf=False)
        respuesta = sin_csrf.post("/api/v1/notificaciones/marcar-todas-leidas/")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(respuesta.json()["code"], "CSRF_INVALID")
