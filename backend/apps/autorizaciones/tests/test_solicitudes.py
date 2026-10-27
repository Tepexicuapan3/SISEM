"""Motor de solicitudes de autorizacion (F3).

Decisiones confirmadas por el usuario (2026-10-27):
  - modalidad por defecto PRIMERO_VALIDO en los 4 tipos, configurable por centro;
  - en MULTIPLE un rechazo resuelve la solicitud como RECHAZADA;
  - una solicitud vence a las 72 horas.
"""
import unittest
from datetime import timedelta
from unittest import mock

from django.db import connection, transaction
from django.test import TestCase
from django.utils import timezone

from apps.autorizaciones import events
from apps.autorizaciones.contracts import cancelar_por_origen, solicitar_autorizacion
from apps.autorizaciones.models import (
    ReglaCentro,
    Solicitud,
    SolicitudDecision,
    SolicitudDestinatario,
    SolicitudItem,
    SolicitudTransicion,
)
from apps.autorizaciones.uses_case.solicitud_use_case import (
    SolicitudError,
    SolicitudUseCase as UseCase,
)

from .fabricas import (
    agregar_alcance,
    asignar_tipo,
    crear_autorizador,
    crear_centro,
    crear_usuario,
    motivo,
    tipo,
)

CLAVE = "Clave_12345"
ITEMS = [
    {"tipoItem": "MEDICAMENTO", "idItemOrigen": 1, "descripcion": "Metilfenidato 10 mg", "cantidad": 30,
     "motivo": "MEDICAMENTO_CONTROLADO"},
]


class _Base(TestCase):
    def setUp(self):
        self.centro = crear_centro()
        self.medico = crear_usuario()
        self.aut_a = self._autorizador()
        self.aut_b = self._autorizador()
        self.auditoria = mock.Mock()
        self.eventos = []
        events.suscribir("SolicitudResuelta", self.eventos.append)
        self.addCleanup(events.desuscribir, "SolicitudResuelta", self.eventos.append)

    def _autorizador(self, clave="REC", centro=None):
        autorizador = crear_autorizador(inicio=timezone.localdate() - timedelta(days=30),
                                        fin=timezone.localdate() + timedelta(days=300))
        agregar_alcance(asignar_tipo(autorizador, clave), "CENTRO", centro or self.centro)
        return autorizador

    def solicitar(self, id_origen=500, items=ITEMS, **extra):
        datos = {
            "clave_tipo": "REC",
            "id_origen": id_origen,
            "folio_origen": "RX-2026-000500",
            "id_centro": self.centro.id,
            "id_usuario_solicitante": self.medico.id_usuario,
            "items": items,
            "motivos": ["MEDICAMENTO_CONTROLADO"],
            "resumen_minimo": {"medicamentos": len(items)},
        }
        datos.update(extra)
        return solicitar_autorizacion(**datos)

    def decidir(self, solicitud, autorizador, decision="APROBAR", *, credencial=CLAVE, version=None, **extra):
        solicitud.refresh_from_db()
        datos = {
            "decision": decision,
            "motivoId": extra.pop("motivoId", None),
            "descripcionMotivo": extra.pop("descripcionMotivo", None),
            "version": solicitud.version if version is None else version,
            "credencial": credencial,
        }
        return UseCase.decidir(
            solicitud.uuid_publico, datos,
            actor=autorizador.usuario, auditoria=self.auditoria, ip="10.0.0.1", agente_usuario="pruebas",
        )

    def assertError(self, codigo, http_status, fn, *args, **kwargs):
        with self.assertRaises(SolicitudError) as capturado:
            fn(*args, **kwargs)
        self.assertEqual(capturado.exception.code, codigo)
        self.assertEqual(capturado.exception.http_status, http_status)
        return capturado.exception


class SolicitarTests(_Base):
    def test_crea_solicitud_pendiente_con_folio_vigencia_y_destinatarios(self):
        solicitud = self.solicitar()

        self.assertEqual(solicitud.estatus, "PENDIENTE")
        self.assertRegex(solicitud.folio, r"^AUT-\d{4}-\d{6}$")
        self.assertEqual(solicitud.modalidad, "PRIMERO_VALIDO")
        self.assertEqual(solicitud.aprobaciones_requeridas, 1)
        self.assertEqual(solicitud.clues, self.centro.code)
        self.assertAlmostEqual(
            (solicitud.fecha_limite - solicitud.fecha_creacion).total_seconds(), 72 * 3600, delta=5,
        )
        self.assertEqual(len(solicitud.hash_contenido), 64)
        self.assertEqual(SolicitudItem.objects.filter(solicitud=solicitud, esta_activo=True).count(), 1)
        destinatarios = set(SolicitudDestinatario.objects.filter(solicitud=solicitud).values_list("autorizador_id", flat=True))
        self.assertEqual(destinatarios, {self.aut_a.pk, self.aut_b.pk})
        self.assertFalse(solicitud.sin_elegibles)
        self.assertEqual(
            list(SolicitudTransicion.objects.filter(solicitud=solicitud).values_list("evento", flat=True)), ["CREADA"],
        )

    def test_el_solicitante_no_se_notifica_a_si_mismo(self):
        solicitud = self.solicitar(id_usuario_solicitante=self.aut_a.usuario_id)
        self.assertFalse(SolicitudDestinatario.objects.filter(solicitud=solicitud, autorizador=self.aut_a).exists())

    def test_regla_del_centro_sobrescribe_modalidad_aprobaciones_y_horas(self):
        ReglaCentro.objects.create(
            tipo_autorizacion=tipo("REC"), centro_atencion=self.centro,
            modalidad="MULTIPLE", aprobaciones_requeridas=2, horas_vigencia_solicitud=24,
        )
        solicitud = self.solicitar()
        self.assertEqual((solicitud.modalidad, solicitud.aprobaciones_requeridas), ("MULTIPLE", 2))
        self.assertAlmostEqual(
            (solicitud.fecha_limite - solicitud.fecha_creacion).total_seconds(), 24 * 3600, delta=5,
        )

    def test_mismo_origen_y_contenido_devuelve_la_misma_solicitud(self):
        primera = self.solicitar()
        segunda = self.solicitar()
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Solicitud.objects.count(), 1)

    def test_si_el_origen_cambia_se_recalcula(self):
        primera = self.solicitar()
        nuevos = ITEMS + [{"tipoItem": "MEDICAMENTO", "idItemOrigen": 2, "descripcion": "Clonazepam",
                           "cantidad": 10, "motivo": "MEDICAMENTO_CONTROLADO"}]
        segunda = self.solicitar(items=nuevos)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertNotEqual(primera.hash_contenido, segunda.hash_contenido)
        self.assertEqual(SolicitudItem.objects.filter(solicitud=segunda, esta_activo=True).count(), 2)
        self.assertEqual(SolicitudItem.objects.filter(solicitud=segunda, esta_activo=False).count(), 1)
        self.assertTrue(SolicitudTransicion.objects.filter(solicitud=segunda, evento="RECALCULADA").exists())

    def test_sin_autorizadores_elegibles_queda_marcada(self):
        otro_centro = crear_centro()
        solicitud = self.solicitar(id_centro=otro_centro.id)
        self.assertTrue(solicitud.sin_elegibles)
        self.assertFalse(SolicitudDestinatario.objects.filter(solicitud=solicitud).exists())

    def test_tipo_inexistente_o_sin_items(self):
        with self.assertRaises(SolicitudError):
            self.solicitar(clave_tipo="XYZ")
        with self.assertRaises(SolicitudError):
            self.solicitar(items=[])


class DecidirPrimeroValidoTests(_Base):
    def setUp(self):
        super().setUp()
        self.solicitud = self.solicitar()

    def test_aprobar_resuelve_la_solicitud_firmada(self):
        resultado = self.decidir(self.solicitud, self.aut_a)

        self.assertEqual(resultado.estatus, "AUTORIZADA")
        self.assertEqual(resultado.id_usuario_resolucion, self.aut_a.usuario_id)
        self.assertIsNotNone(resultado.fecha_resolucion)
        decision = SolicitudDecision.objects.get(solicitud=resultado)
        self.assertEqual(decision.metodo_firma, "SIMPLE")
        self.assertEqual(decision.hash_contenido, resultado.hash_contenido)
        self.assertTrue(decision.numero_cedula.startswith("CED"))
        self.assertEqual(decision.alcance_aplicado, "CENTRO")
        self.assertEqual(decision.ip_origen, "10.0.0.1")
        estatus = dict(SolicitudDestinatario.objects.filter(solicitud=resultado).values_list("autorizador_id", "estatus"))
        self.assertEqual(estatus, {self.aut_a.pk: "DECIDIO", self.aut_b.pk: "ATENDIDA_POR_OTRO"})
        self.assertEqual(self.auditoria.call_args.args[0], "SolicitudAutorizada")

    def test_evento_de_resolucion_para_el_dominio_origen(self):
        self.decidir(self.solicitud, self.aut_a)
        self.assertEqual(len(self.eventos), 1)
        evento = self.eventos[0]
        self.assertEqual((evento.tipo_origen, evento.id_origen, evento.estatus), ("RECETA", 500, "AUTORIZADA"))

    def test_rechazo_exige_motivo_de_rechazo(self):
        self.assertError("REASON_REQUIRED", 400, self.decidir, self.solicitud, self.aut_a, "RECHAZAR")
        self.assertError(
            "REASON_REQUIRED", 400, self.decidir, self.solicitud, self.aut_a, "RECHAZAR",
            motivoId=motivo("RECHAZO", "OTRO").id_motivo,
        )
        rechazada = self.decidir(
            self.solicitud, self.aut_a, "RECHAZAR", motivoId=motivo("RECHAZO", "NO_JUSTIFICADO").id_motivo,
        )
        self.assertEqual(rechazada.estatus, "RECHAZADA")
        self.assertEqual(rechazada.motivo_cierre.clave, "NO_JUSTIFICADO")

    def test_una_solicitud_resuelta_no_se_vuelve_a_decidir(self):
        self.decidir(self.solicitud, self.aut_a)
        self.assertError("ALREADY_RESOLVED", 409, self.decidir, self.solicitud, self.aut_b)

    def test_version_desactualizada(self):
        self.assertError("STALE_VERSION", 409, self.decidir, self.solicitud, self.aut_a, version=99)

    def test_contrasena_incorrecta_no_guarda_nada(self):
        self.assertError("REAUTH_FAILED", 403, self.decidir, self.solicitud, self.aut_a, credencial="mala")
        self.assertFalse(SolicitudDecision.objects.exists())
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estatus, "PENDIENTE")

    def test_quien_no_cumple_la_politica_recibe_el_motivo(self):
        de_laboratorio = self._autorizador(clave="LAB")
        error = self.assertError("NOT_AUTHORIZED", 403, self.decidir, self.solicitud, de_laboratorio)
        self.assertEqual(error.details["motivo"], "TIPO_NO_ASIGNADO")

    def test_quien_origino_no_puede_autorizar(self):
        propia = self.solicitar(id_origen=900, id_usuario_solicitante=self.aut_a.usuario_id)
        error = self.assertError("NOT_AUTHORIZED", 403, self.decidir, propia, self.aut_a)
        self.assertEqual(error.details["motivo"], "AUTOAUTORIZACION")

    def test_autorizador_habilitado_que_no_fue_notificado_tambien_puede_decidir(self):
        nuevo = self._autorizador()
        resultado = self.decidir(self.solicitud, nuevo)
        self.assertEqual(resultado.estatus, "AUTORIZADA")
        self.assertEqual(
            SolicitudDestinatario.objects.get(solicitud=resultado, autorizador=nuevo).tipo_seleccion, "DIRECTO",
        )

    def test_tipo_que_no_permite_rechazo(self):
        rec = tipo("REC")
        rec.permite_rechazo = False
        rec.save()
        self.assertError(
            "REJECTION_NOT_ALLOWED", 409, self.decidir, self.solicitud, self.aut_a, "RECHAZAR",
            motivoId=motivo("RECHAZO", "NO_JUSTIFICADO").id_motivo,
        )


class DecidirMultipleTests(_Base):
    def setUp(self):
        super().setUp()
        ReglaCentro.objects.create(
            tipo_autorizacion=tipo("REC"), centro_atencion=self.centro, modalidad="MULTIPLE", aprobaciones_requeridas=2,
        )
        self.solicitud = self.solicitar()

    def test_requiere_las_aprobaciones_configuradas(self):
        parcial = self.decidir(self.solicitud, self.aut_a)
        self.assertEqual(parcial.estatus, "PENDIENTE")
        self.assertTrue(SolicitudTransicion.objects.filter(solicitud=parcial, evento="APROBACION_PARCIAL").exists())
        self.assertEqual(self.eventos, [])

        final = self.decidir(self.solicitud, self.aut_b)
        self.assertEqual(final.estatus, "AUTORIZADA")

    def test_no_se_aprueba_dos_veces(self):
        self.decidir(self.solicitud, self.aut_a)
        self.assertError("DUPLICATE_DECISION", 409, self.decidir, self.solicitud, self.aut_a)

    def test_un_rechazo_resuelve_aunque_haya_aprobaciones(self):
        self.decidir(self.solicitud, self.aut_a)
        rechazada = self.decidir(
            self.solicitud, self.aut_b, "RECHAZAR", motivoId=motivo("RECHAZO", "DUPLICADO").id_motivo,
        )
        self.assertEqual(rechazada.estatus, "RECHAZADA")

    def test_responsable_obligatorio(self):
        SolicitudDestinatario.objects.filter(solicitud=self.solicitud, autorizador=self.aut_b).update(es_obligatorio=True)
        ReglaCentro.objects.update(aprobaciones_requeridas=1)
        Solicitud.objects.filter(pk=self.solicitud.pk).update(aprobaciones_requeridas=1)

        self.assertEqual(self.decidir(self.solicitud, self.aut_a).estatus, "PENDIENTE")
        self.assertEqual(self.decidir(self.solicitud, self.aut_b).estatus, "AUTORIZADA")

    def test_si_el_origen_cambia_las_aprobaciones_previas_dejan_de_contar(self):
        self.decidir(self.solicitud, self.aut_a)
        self.solicitar(items=ITEMS + [{"tipoItem": "MEDICAMENTO", "idItemOrigen": 3, "descripcion": "Otro",
                                       "cantidad": 1, "motivo": "MEDICAMENTO_ESPECIAL"}])
        self.assertEqual(self.decidir(self.solicitud, self.aut_b).estatus, "PENDIENTE")
        self.assertEqual(self.decidir(self.solicitud, self.aut_a).estatus, "AUTORIZADA")


class VencimientoYCancelacionTests(_Base):
    def test_las_pendientes_vencidas_pasan_a_vencida(self):
        vencida = self.solicitar(id_origen=1)
        vigente = self.solicitar(id_origen=2)
        Solicitud.objects.filter(pk=vencida.pk).update(fecha_limite=timezone.now() - timedelta(minutes=1))

        self.assertEqual(UseCase.vencer_pendientes(), 1)
        vencida.refresh_from_db()
        vigente.refresh_from_db()
        self.assertEqual((vencida.estatus, vigente.estatus), ("VENCIDA", "PENDIENTE"))
        self.assertTrue(SolicitudTransicion.objects.filter(solicitud=vencida, evento="VENCIDA").exists())
        self.assertError("ALREADY_RESOLVED", 409, self.decidir, vencida, self.aut_a)

    def test_vencer_es_idempotente(self):
        solicitud = self.solicitar()
        Solicitud.objects.filter(pk=solicitud.pk).update(fecha_limite=timezone.now() - timedelta(minutes=1))
        UseCase.vencer_pendientes()
        self.assertEqual(UseCase.vencer_pendientes(), 0)

    def test_cancelar_por_origen(self):
        solicitud = self.solicitar()
        self.assertTrue(cancelar_por_origen("RECETA", 500, id_usuario=self.medico.id_usuario))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estatus, "CANCELADA")
        self.assertFalse(cancelar_por_origen("RECETA", 500, id_usuario=self.medico.id_usuario))


@unittest.skipUnless(connection.vendor == "postgresql", "requiere Postgres (TESTS_EN_POSTGRES=1)")
class DecisionesSoloInsercionTests(_Base):
    def test_decision_firmada_y_transiciones_no_se_alteran(self):
        solicitud = self.solicitar()
        self.decidir(solicitud, self.aut_a)
        for consulta in (
            lambda: SolicitudDecision.objects.filter(solicitud=solicitud).update(decision="RECHAZAR"),
            lambda: SolicitudDecision.objects.filter(solicitud=solicitud).delete(),
            lambda: SolicitudTransicion.objects.filter(solicitud=solicitud).update(evento="ALTERADA"),
        ):
            with self.assertRaises(Exception):
                with transaction.atomic():
                    consulta()
