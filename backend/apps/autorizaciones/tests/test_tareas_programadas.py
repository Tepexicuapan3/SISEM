"""F7: tareas programadas del modulo de autorizaciones.

Decisiones del usuario (2026-10-28):
  - Escalamiento: a las 24 h (configurable por tipo) recuerda a los destinatarios
    y suma a los elegibles que faltaban; una sola vez; sin nadie, avisa al solicitante.
  - Vencimiento del autorizador: queda en el historial y se avisa; el estatus no cambia.
  - Aviso por vencer: al autorizador y a los administradores, una vez por fecha de fin.
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.autorizaciones import events, tasks
from apps.autorizaciones.contracts import solicitar_autorizacion
from apps.autorizaciones.models import (
    Autorizador,
    AutorizadorMovimiento,
    Solicitud,
    SolicitudDestinatario,
    SolicitudTransicion,
    TipoAutorizacion,
)
from apps.autorizaciones.uses_case.solicitud_use_case import SolicitudUseCase
from apps.autorizaciones.uses_case.vigencia_autorizadores_use_case import (
    avisar_por_vencer,
    registrar_vencidos,
)
from apps.catalogos.models import CatPermiso, CatRol
from apps.notificaciones.models import Entrega, Notificacion
from apps.notificaciones.services import notificacion_service

from .fabricas import agregar_alcance, asignar_tipo, crear_autorizador, crear_centro, crear_usuario, motivo

ITEMS = [{"tipoItem": "MEDICAMENTO", "idItemOrigen": 1, "descripcion": "Metilfenidato 10 mg", "cantidad": 30,
          "motivo": "MEDICAMENTO_CONTROLADO"}]


def _con_rol(usuario, *, permisos=(), es_admin=False):
    rol = CatRol.objects.create(
        rol=f"ROL_{usuario.usuario}", desc_rol="rol de prueba", landing_route="/", is_active=True,
        is_admin=es_admin,
    )
    for codigo in permisos:
        permiso, _ = CatPermiso.objects.get_or_create(codigo=codigo, defaults={"descripcion": codigo, "is_active": True})
        RelRolPermiso.objects.create(id_rol=rol, id_permiso=permiso)
    RelUsuarioRol.objects.create(id_usuario=usuario, id_rol=rol, is_primary=True)
    return usuario


def _avisados(categoria, desde=0):
    """Usuarios notificados con esa categoria despues de la notificacion `desde`."""
    return set(
        Notificacion.objects.filter(categoria=categoria, pk__gt=desde).values_list("usuario_id", flat=True)
    )


class _SinEnvios(TestCase):
    def setUp(self):
        for nombre in ("_publicar_tiempo_real", "_encolar_correo"):
            parche = mock.patch.object(notificacion_service, nombre)
            parche.start()
            self.addCleanup(parche.stop)
        self.hoy = timezone.localdate()


# --------------------------------------------------------------------- #
# Escalamiento de solicitudes                                            #
# --------------------------------------------------------------------- #

class EscalamientoTests(_SinEnvios):
    def setUp(self):
        super().setUp()
        self.centro = crear_centro()
        self.medico = crear_usuario()
        self.notificado = self._autorizador()

    def _autorizador(self):
        autorizador = crear_autorizador(inicio=self.hoy - timedelta(days=30), fin=self.hoy + timedelta(days=300))
        agregar_alcance(asignar_tipo(autorizador, "REC"), "CENTRO", self.centro)
        return autorizador

    def _solicitar(self, id_origen=700, horas_atras=25):
        solicitud = solicitar_autorizacion(
            clave_tipo="REC", id_origen=id_origen, id_centro=self.centro.id,
            id_usuario_solicitante=self.medico.id_usuario, items=ITEMS, motivos=["MEDICAMENTO_CONTROLADO"],
        )
        Solicitud.objects.filter(pk=solicitud.pk).update(
            fecha_creacion=timezone.now() - timedelta(hours=horas_atras),
        )
        # Solo cuentan las notificaciones del escalamiento.
        self.marca = Notificacion.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
        return solicitud

    def _avisados(self, categoria):
        return _avisados(categoria, self.marca)

    def test_a_las_24_horas_recuerda_y_suma_a_los_elegibles_que_faltaban(self):
        solicitud = self._solicitar()
        nuevo = self._autorizador()  # alta posterior a la solicitud

        self.assertEqual(SolicitudUseCase.escalar_pendientes(), 1)

        self.assertEqual(self._avisados("AUT_RECORDATORIO"), {self.notificado.usuario_id})
        self.assertEqual(self._avisados("AUT_SOLICITADA"), {nuevo.usuario_id})
        destinatario = SolicitudDestinatario.objects.get(solicitud=solicitud, autorizador=nuevo)
        self.assertEqual(destinatario.tipo_seleccion, "ESCALAMIENTO")
        solicitud.refresh_from_db()
        self.assertIsNotNone(solicitud.fecha_escalamiento)
        self.assertEqual(solicitud.estatus, "PENDIENTE")
        self.assertTrue(SolicitudTransicion.objects.filter(solicitud=solicitud, evento="ESCALADA").exists())

    def test_se_escala_una_sola_vez(self):
        self._solicitar()
        SolicitudUseCase.escalar_pendientes()

        self.assertEqual(SolicitudUseCase.escalar_pendientes(), 0)

    def test_antes_de_las_horas_del_tipo_no_escala(self):
        self._solicitar(horas_atras=23)

        self.assertEqual(SolicitudUseCase.escalar_pendientes(), 0)

    def test_las_horas_se_configuran_por_tipo(self):
        TipoAutorizacion.objects.filter(clave="REC").update(horas_escalamiento=4)
        self._solicitar(horas_atras=5)

        self.assertEqual(SolicitudUseCase.escalar_pendientes(), 1)

    def test_las_resueltas_no_se_escalan(self):
        solicitud = self._solicitar()
        Solicitud.objects.filter(pk=solicitud.pk).update(estatus="CANCELADA")

        self.assertEqual(SolicitudUseCase.escalar_pendientes(), 0)

    def test_sin_nadie_que_la_atienda_avisa_al_solicitante(self):
        self._solicitar()
        # El unico destinatario ya no puede autorizar: no se le recuerda.
        Autorizador.objects.filter(pk=self.notificado.pk).update(fecha_fin_vigencia=self.hoy - timedelta(days=1))

        SolicitudUseCase.escalar_pendientes()

        self.assertEqual(self._avisados("AUT_SIN_ELEGIBLES"), {self.medico.id_usuario})
        self.assertEqual(self._avisados("AUT_RECORDATORIO"), set())

    def test_no_se_suma_al_solicitante_aunque_sea_autorizador(self):
        solicitante = crear_autorizador(
            self.medico, inicio=self.hoy - timedelta(days=30), fin=self.hoy + timedelta(days=300),
        )
        agregar_alcance(asignar_tipo(solicitante, "REC"), "CENTRO", self.centro)
        solicitud = self._solicitar()

        SolicitudUseCase.escalar_pendientes()

        self.assertFalse(SolicitudDestinatario.objects.filter(solicitud=solicitud, autorizador=solicitante).exists())


# --------------------------------------------------------------------- #
# Vigencia de los autorizadores                                          #
# --------------------------------------------------------------------- #

class VigenciaAutorizadoresTests(_SinEnvios):
    def setUp(self):
        super().setUp()
        self.admin = _con_rol(crear_usuario(), es_admin=True)
        self.gestor = _con_rol(crear_usuario(), permisos=["admin:autorizadores:update"])
        _con_rol(crear_usuario(), permisos=["admin:autorizadores:read"])  # solo lectura: no se avisa

    def _autorizador(self, dias_para_fin, **extra):
        return crear_autorizador(
            inicio=self.hoy - timedelta(days=100), fin=self.hoy + timedelta(days=dias_para_fin), **extra,
        )

    def test_avisa_por_vencer_al_autorizador_y_a_quienes_pueden_renovar(self):
        por_vencer = self._autorizador(10)
        self._autorizador(40)  # lejos del aviso

        self.assertEqual(avisar_por_vencer(self.hoy), 1)

        self.assertEqual(
            _avisados("AUT_AUTORIZADOR_POR_VENCER"),
            {por_vencer.usuario_id, self.admin.id_usuario, self.gestor.id_usuario},
        )
        movimiento = AutorizadorMovimiento.objects.get(autorizador=por_vencer, tipo_movimiento="AVISO_POR_VENCER")
        self.assertIsNone(movimiento.id_usuario_responsable)

    def test_el_aviso_es_uno_por_fecha_de_fin_y_vuelve_tras_renovar(self):
        autorizador = self._autorizador(10)
        avisar_por_vencer(self.hoy)

        self.assertEqual(avisar_por_vencer(self.hoy), 0)

        Autorizador.objects.filter(pk=autorizador.pk).update(fecha_fin_vigencia=self.hoy + timedelta(days=5))
        self.assertEqual(avisar_por_vencer(self.hoy), 1)

    def test_no_avisa_a_inactivos_ni_a_vencidos(self):
        self._autorizador(10, estatus="INACTIVO", motivo_estatus=motivo("BAJA", "BAJA_LABORAL"))
        self._autorizador(-1)

        self.assertEqual(avisar_por_vencer(self.hoy), 0)

    def test_registra_el_vencimiento_una_vez_sin_cambiar_el_estatus(self):
        vencido = self._autorizador(-1)
        self._autorizador(5)

        self.assertEqual(registrar_vencidos(self.hoy), 1)
        self.assertEqual(registrar_vencidos(self.hoy), 0)

        vencido.refresh_from_db()
        self.assertEqual(vencido.estatus, "ACTIVO")
        self.assertEqual(
            AutorizadorMovimiento.objects.filter(autorizador=vencido, tipo_movimiento="VENCIMIENTO").count(), 1,
        )
        self.assertEqual(
            _avisados("AUT_AUTORIZADOR_VENCIDO"),
            {vencido.usuario_id, self.admin.id_usuario, self.gestor.id_usuario},
        )

    def test_un_vencimiento_con_otra_fecha_de_fin_se_registra_de_nuevo(self):
        vencido = self._autorizador(-1)
        registrar_vencidos(self.hoy)

        # Se renovo y volvio a vencer: es otro vencimiento.
        Autorizador.objects.filter(pk=vencido.pk).update(fecha_fin_vigencia=self.hoy - timedelta(days=2))

        self.assertEqual(registrar_vencidos(self.hoy), 1)


# --------------------------------------------------------------------- #
# Reintento de correos                                                   #
# --------------------------------------------------------------------- #

class ReintentoCorreosTests(TestCase):
    def setUp(self):
        usuario = crear_usuario()
        with mock.patch.object(notificacion_service, "_publicar_tiempo_real"), \
                mock.patch.object(notificacion_service, "_encolar_correo"):
            self.notificacion = notificacion_service.notificar(
                [usuario.id_usuario], categoria="AUT_SOLICITADA", titulo="t", cuerpo="c",
                tipo_recurso="solicitud_autorizacion", referencia_recurso="x", url_accion="/x",
            )[0]
        self.correo = Entrega.objects.get(notificacion=self.notificacion, canal="CORREO")

    def _falla(self, intentos):
        Entrega.objects.filter(pk=self.correo.pk).update(estatus="FALLIDA", intentos=intentos)

    def test_reencola_los_fallidos_con_intentos_disponibles(self):
        self._falla(1)

        with mock.patch.object(notificacion_service, "_encolar_correo") as encolar:
            self.assertEqual(notificacion_service.reintentar_correos_fallidos(), 1)

        encolar.assert_called_once_with([self.notificacion.pk])

    def test_no_reintenta_despues_de_tres_intentos(self):
        self._falla(3)

        with mock.patch.object(notificacion_service, "_encolar_correo") as encolar:
            self.assertEqual(notificacion_service.reintentar_correos_fallidos(), 0)

        encolar.assert_not_called()

    def test_no_reintenta_los_enviados(self):
        Entrega.objects.filter(pk=self.correo.pk).update(estatus="ENVIADA", intentos=1)

        with mock.patch.object(notificacion_service, "_encolar_correo") as encolar:
            self.assertEqual(notificacion_service.reintentar_correos_fallidos(), 0)


class TareasCeleryTests(TestCase):
    def test_las_tareas_delegan_en_los_casos_de_uso(self):
        with mock.patch.object(SolicitudUseCase, "escalar_pendientes", return_value=2):
            self.assertEqual(tasks.escalar_solicitudes_pendientes(), {"escaladas": 2})
        with mock.patch.object(tasks, "avisar_por_vencer", return_value=1), \
                mock.patch.object(tasks, "registrar_vencidos", return_value=3):
            self.assertEqual(tasks.revisar_vigencia_autorizadores(), {"porVencer": 1, "vencidos": 3})
