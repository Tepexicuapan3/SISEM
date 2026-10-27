"""Contrato del modulo para otros dominios (F2): puede_autorizar y elegibles.

Lee el estado real en la base en cada llamada: un cambio de estatus, una
baja de centro o una cedula borrada en Usuarios aplica de inmediato.
"""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuarioCedula
from apps.autorizaciones.contracts import autorizadores_elegibles, puede_autorizar
from apps.autorizaciones.domain.politica import Motivo
from apps.autorizaciones.models import Autorizador

from .fabricas import agregar_alcance, asignar_tipo, crear_autorizador, crear_centro, crear_usuario, motivo

HOY = date(2026, 6, 15)


class PuedeAutorizarTests(TestCase):
    def setUp(self):
        self.centro = crear_centro()
        self.autorizador = crear_autorizador()
        self.rec = asignar_tipo(self.autorizador, "REC")
        agregar_alcance(self.rec, "CENTRO", self.centro)
        self.usuario = self.autorizador.usuario_id

    def test_habilitado(self):
        decision = puede_autorizar(self.usuario, "REC", self.centro.id, fecha=HOY)
        self.assertTrue(decision)
        self.assertEqual(decision.id_autorizador, self.autorizador.pk)
        self.assertEqual(decision.id_autorizador_tipo, self.rec.pk)

    def test_otro_tipo_no_habilita(self):
        self.assertEqual(puede_autorizar(self.usuario, "LAB", self.centro.id, fecha=HOY).motivo, Motivo.TIPO_NO_ASIGNADO)

    def test_centro_inexistente_o_no_asignado(self):
        self.assertEqual(puede_autorizar(self.usuario, "REC", 999999, fecha=HOY).motivo, Motivo.CENTRO_NO_ENCONTRADO)
        otro = crear_centro()
        self.assertEqual(puede_autorizar(self.usuario, "REC", otro.id, fecha=HOY).motivo, Motivo.CENTRO_NO_ASIGNADO)

    def test_usuario_que_no_es_autorizador(self):
        self.assertEqual(
            puede_autorizar(crear_usuario().id_usuario, "REC", self.centro.id, fecha=HOY).motivo,
            Motivo.NO_ES_AUTORIZADOR,
        )

    def test_suspension_aplica_de_inmediato(self):
        Autorizador.objects.filter(pk=self.autorizador.pk).update(
            estatus="SUSPENDIDO", motivo_estatus=motivo("SUSPENSION", "LICENCIA"),
        )
        self.assertEqual(
            puede_autorizar(self.usuario, "REC", self.centro.id, fecha=HOY).motivo, Motivo.AUTORIZADOR_SUSPENDIDO,
        )

    def test_dado_de_baja(self):
        Autorizador.objects.filter(pk=self.autorizador.pk).update(
            estatus="INACTIVO", motivo_estatus=motivo("BAJA", "BAJA_LABORAL"),
            esta_activo=False, fecha_baja=timezone.now(),
        )
        self.assertEqual(
            puede_autorizar(self.usuario, "REC", self.centro.id, fecha=HOY).motivo, Motivo.AUTORIZADOR_INACTIVO,
        )

    def test_vigencia_se_evalua_en_cada_llamada(self):
        self.assertEqual(
            puede_autorizar(self.usuario, "REC", self.centro.id, fecha=date(2027, 1, 1)).motivo,
            Motivo.VIGENCIA_VENCIDA,
        )

    def test_centro_retirado_por_baja_logica(self):
        alcance = self.rec.alcances.get()
        alcance.esta_activo = False
        alcance.fecha_baja = timezone.now()
        alcance.save()
        self.assertEqual(
            puede_autorizar(self.usuario, "REC", self.centro.id, fecha=HOY).motivo, Motivo.CENTRO_NO_ASIGNADO,
        )

    def test_tipo_retirado_por_baja_logica(self):
        self.rec.esta_activo = False
        self.rec.fecha_baja = timezone.now()
        self.rec.save()
        self.assertEqual(puede_autorizar(self.usuario, "REC", self.centro.id, fecha=HOY).motivo, Motivo.TIPO_NO_ASIGNADO)

    def test_cedula_borrada_en_usuarios(self):
        DetUsuarioCedula.objects.filter(id_usuario_id=self.usuario).delete()
        self.assertEqual(puede_autorizar(self.usuario, "REC", self.centro.id, fecha=HOY).motivo, Motivo.CEDULA_REQUERIDA)

    def test_autoautorizacion(self):
        decision = puede_autorizar(
            self.usuario, "REC", self.centro.id, fecha=HOY, id_usuario_solicitante=self.usuario,
        )
        self.assertEqual(decision.motivo, Motivo.AUTOAUTORIZACION)

    def test_cedula_con_la_que_firma(self):
        decision = puede_autorizar(self.usuario, "REC", self.centro.id, fecha=HOY)
        self.assertTrue(decision.numero_cedula.startswith("CED"))

    def test_datos_faltantes_no_autorizan(self):
        self.assertFalse(puede_autorizar(None, "REC", self.centro.id, fecha=HOY))
        self.assertFalse(puede_autorizar(self.usuario, "", self.centro.id, fecha=HOY))


class AutorizadoresElegiblesTests(TestCase):
    def setUp(self):
        self.clinica = crear_centro("CLINICA")
        self.hospital = crear_centro("HOSPITAL")

    def _autorizador(self, alcance, valor=None, clave="LAB", **extra):
        autorizador = crear_autorizador(**extra)
        agregar_alcance(asignar_tipo(autorizador, clave), alcance, valor)
        return autorizador

    def test_incluye_cobertura_por_centro_tipo_de_centro_y_global(self):
        por_centro = self._autorizador("CENTRO", self.clinica)
        por_tipo = self._autorizador("TIPO_CENTRO", "CLINICA")
        global_ = self._autorizador("GLOBAL")
        otro_centro = self._autorizador("CENTRO", self.hospital)
        otro_tipo = self._autorizador("CENTRO", self.clinica, clave="REC")

        ids = {e.id_usuario for e in autorizadores_elegibles("LAB", self.clinica.id, fecha=HOY)}
        self.assertEqual(ids, {por_centro.usuario_id, por_tipo.usuario_id, global_.usuario_id})
        self.assertNotIn(otro_centro.usuario_id, ids)
        self.assertNotIn(otro_tipo.usuario_id, ids)

    def test_excluye_suspendidos_vencidos_y_al_solicitante(self):
        vigente = self._autorizador("CENTRO", self.clinica)
        self._autorizador(
            "CENTRO", self.clinica, estatus="SUSPENDIDO", motivo_estatus=motivo("SUSPENSION", "LICENCIA"),
        )
        self._autorizador("CENTRO", self.clinica, inicio=date(2025, 1, 1), fin=date(2025, 12, 31))
        solicitante = self._autorizador("CENTRO", self.clinica)

        ids = {
            e.id_usuario
            for e in autorizadores_elegibles(
                "LAB", self.clinica.id, fecha=HOY, excluir_id_usuario=solicitante.usuario_id,
            )
        }
        self.assertEqual(ids, {vigente.usuario_id})

    def test_cada_elegible_pasa_la_misma_politica(self):
        for elegible in autorizadores_elegibles("LAB", self.clinica.id, fecha=HOY):
            self.assertTrue(puede_autorizar(elegible.id_usuario, "LAB", self.clinica.id, fecha=HOY))

    def test_centro_inexistente_no_tiene_elegibles(self):
        self._autorizador("GLOBAL")
        self.assertEqual(autorizadores_elegibles("LAB", 999999, fecha=HOY), [])
