"""Notificaciones del flujo de autorizacion (F4) y envio manual a autorizadores.

Las notificaciones solo llevan folio, tipo, centro y fecha (sin datos del
paciente) y un enlace que solo navega al detalle.
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.autorizaciones.contracts import solicitar_autorizacion
from apps.autorizaciones.models import Solicitud, SolicitudDestinatario, SolicitudTransicion
from apps.autorizaciones.uses_case.solicitud_use_case import SolicitudUseCase
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import notificacion_service

from .fabricas import agregar_alcance, asignar_tipo, crear_autorizador, crear_centro, crear_usuario, motivo
from .test_solicitudes_api import _cliente

CLAVE = "Clave_12345"
ITEMS = [{"tipoItem": "ESTUDIO", "idItemOrigen": 9, "descripcion": "Tomografía de cráneo", "cantidad": 1,
          "motivo": "ESTUDIO_MARCADO"}]


class _Base(APITestCase):
    def setUp(self):
        cache.clear()
        for nombre in ("_publicar_tiempo_real", "_encolar_correo"):
            parche = mock.patch.object(notificacion_service, nombre)
            parche.start()
            self.addCleanup(parche.stop)
        hoy = timezone.localdate()
        self.centro = crear_centro()
        self.medico = crear_usuario()
        self.a = crear_autorizador(inicio=hoy - timedelta(days=5), fin=hoy + timedelta(days=100))
        self.b = crear_autorizador(inicio=hoy - timedelta(days=5), fin=hoy + timedelta(days=100))
        for autorizador in (self.a, self.b):
            agregar_alcance(asignar_tipo(autorizador, "GAB"), "CENTRO", self.centro)

    def solicitar(self, **extra):
        datos = dict(
            clave_tipo="GAB", id_origen=31, folio_origen="REF-2026-000031", id_centro=self.centro.id,
            id_usuario_solicitante=self.medico.id_usuario, items=ITEMS, motivos=["ESTUDIO_MARCADO"],
            resumen_minimo={"estudios": 1}, id_paciente=8080,
        )
        datos.update(extra)
        return solicitar_autorizacion(**datos)

    def notificaciones(self, usuario, categoria=None):
        consulta = Notificacion.objects.filter(usuario_id=usuario.usuario_id if hasattr(usuario, "usuario_id") else usuario.id_usuario)
        return consulta.filter(categoria=categoria) if categoria else consulta


class FlujoTests(_Base):
    def test_al_crear_se_notifica_a_los_autorizadores_elegibles(self):
        solicitud = self.solicitar()
        for autorizador in (self.a, self.b):
            notificacion = self.notificaciones(autorizador, "AUT_SOLICITADA").get()
            self.assertEqual(notificacion.url_accion, f"/clinico/autorizaciones/{solicitud.uuid_publico}")
            self.assertIn(solicitud.folio, notificacion.cuerpo)
            self.assertIn("Gabinete", notificacion.cuerpo)
            self.assertIn(self.centro.name, notificacion.cuerpo)
            self.assertNotIn("8080", notificacion.cuerpo + notificacion.titulo)
            self.assertNotIn("Tomografía", notificacion.cuerpo)

    def test_sin_elegibles_se_avisa_al_solicitante(self):
        self.solicitar(id_centro=crear_centro().id)
        self.assertTrue(self.notificaciones(self.medico, "AUT_SIN_ELEGIBLES").exists())

    def test_al_resolver_se_avisa_al_solicitante_y_a_los_demas(self):
        solicitud = self.solicitar()
        SolicitudUseCase.decidir(
            solicitud.uuid_publico, {"decision": "APROBAR", "version": solicitud.version, "credencial": CLAVE},
            actor=self.a.usuario, auditoria=mock.Mock(),
        )
        resuelta = self.notificaciones(self.medico, "AUT_RESUELTA").get()
        self.assertIn("autorizada", resuelta.titulo.lower())
        self.assertTrue(self.notificaciones(self.b, "AUT_ATENDIDA_POR_OTRO").exists())
        self.assertFalse(self.notificaciones(self.a, "AUT_ATENDIDA_POR_OTRO").exists())

    def test_al_vencer_se_avisa_a_todos(self):
        solicitud = self.solicitar()
        Solicitud.objects.filter(pk=solicitud.pk).update(fecha_limite=timezone.now() - timedelta(minutes=1))
        SolicitudUseCase.vencer_pendientes()
        self.assertTrue(self.notificaciones(self.medico, "AUT_VENCIDA").exists())
        self.assertTrue(self.notificaciones(self.a, "AUT_VENCIDA").exists())


class EnvioManualTests(_Base):
    def setUp(self):
        super().setUp()
        self.solicitud = self.solicitar()
        self.base = f"/api/v1/autorizaciones/solicitudes/{self.solicitud.uuid_publico}/"
        hoy = timezone.localdate()
        self.c = crear_autorizador(inicio=hoy - timedelta(days=5), fin=hoy + timedelta(days=100))
        agregar_alcance(asignar_tipo(self.c, "GAB"), "CENTRO", self.centro)
        self.cliente = _cliente(self.a.usuario, ["clinico:autorizaciones:read", "clinico:autorizaciones:notify"])

    def test_lista_elegibles_e_indica_quien_ya_fue_notificado(self):
        respuesta = self.cliente.get(f"{self.base}elegibles/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        notificado = {e["idAutorizador"]: e["yaNotificado"] for e in respuesta.json()["items"]}
        self.assertEqual(notificado, {self.a.pk: True, self.b.pk: True, self.c.pk: False})

    def test_enviar_a_un_autorizador_elegido(self):
        respuesta = self.cliente.post(f"{self.base}notificar/", {"autorizadorIds": [self.c.pk]}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content)
        destinatario = SolicitudDestinatario.objects.get(solicitud=self.solicitud, autorizador=self.c)
        self.assertEqual((destinatario.tipo_seleccion, destinatario.id_usuario_envio),
                         ("MANUAL", self.a.usuario_id))
        self.assertTrue(self.notificaciones(self.c, "AUT_SOLICITADA").exists())
        self.assertTrue(SolicitudTransicion.objects.filter(solicitud=self.solicitud, evento="NOTIFICADA").exists())

    def test_reenviar_a_todos_los_elegibles(self):
        respuesta = self.cliente.post(f"{self.base}notificar/", {"todosElegibles": True}, format="json")
        self.assertEqual(respuesta.json()["notificados"], 3)
        self.assertEqual(self.notificaciones(self.b, "AUT_SOLICITADA").count(), 2)

    def test_no_se_envia_a_quien_no_es_elegible(self):
        de_laboratorio = crear_autorizador()
        agregar_alcance(asignar_tipo(de_laboratorio, "LAB"), "CENTRO", self.centro)
        respuesta = self.cliente.post(f"{self.base}notificar/", {"autorizadorIds": [de_laboratorio.pk]}, format="json")
        self.assertEqual(respuesta.status_code, 422)
        self.assertEqual(respuesta.json()["code"], "RECIPIENT_NOT_ELIGIBLE")

    def test_solicitud_resuelta_no_se_reenvia(self):
        SolicitudUseCase.decidir(
            self.solicitud.uuid_publico,
            {"decision": "RECHAZAR", "version": self.solicitud.version, "credencial": CLAVE,
             "motivoId": motivo("RECHAZO", "DUPLICADO").id_motivo},
            actor=self.b.usuario, auditoria=mock.Mock(),
        )
        respuesta = self.cliente.post(f"{self.base}notificar/", {"todosElegibles": True}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)

    def test_exige_permiso_de_envio(self):
        solo_lectura = _cliente(self.b.usuario, ["clinico:autorizaciones:read"])
        respuesta = solo_lectura.post(f"{self.base}notificar/", {"todosElegibles": True}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
