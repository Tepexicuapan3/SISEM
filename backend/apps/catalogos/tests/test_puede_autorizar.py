"""Politica puede_autorizar (S3-S8, S11-S13)."""
from datetime import date, timedelta

from django.test import TestCase

from apps.catalogos.models import CatCentroAtencion
from apps.catalogos.models.designacion_autorizador import TIPO_CANCELAR_NOTA
from apps.catalogos.services.designacion_autorizador_service import puede_autorizar

from .designacion_factories import (
    add_scope,
    get_tipo,
    make_center,
    make_designation,
    make_user,
)

CLINICA = CatCentroAtencion.TipoCentro.CLINICA
HOSPITAL = CatCentroAtencion.TipoCentro.HOSPITAL
HOY = date(2026, 6, 15)


class PuedeAutorizarTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.clinica_a = make_center(CLINICA)
        self.clinica_b = make_center(CLINICA)
        self.hospital = make_center(HOSPITAL)

    def _can(self, center, fecha=HOY, tipo=TIPO_CANCELAR_NOTA, user=None):
        return puede_autorizar((user or self.user).id_usuario, tipo, center.id, fecha)

    # --- Alcance -----------------------------------------------------------
    def test_s3_solo_centros_designados_aunque_sean_del_mismo_tipo(self):
        c1, c2, c3, c4 = (make_center(CLINICA) for _ in range(4))
        make_designation(self.user, scopes=[("CENTRO", c1), ("CENTRO", c2), ("CENTRO", c3)])
        for centro in (c1, c2, c3):
            self.assertTrue(self._can(centro))
        self.assertFalse(self._can(c4))

    def test_s4_tipo_centro_cubre_centros_creados_despues(self):
        make_designation(self.user, scopes=[("TIPO_CENTRO", "CLINICA")])
        self.assertTrue(self._can(self.clinica_a))
        nueva = make_center(CLINICA)  # alta posterior a la designacion
        decision = self._can(nueva)
        self.assertTrue(decision)
        self.assertEqual(decision.alcance_aplicado, "TIPO_CENTRO")
        self.assertFalse(self._can(self.hospital))

    def test_s5_items_combinados(self):
        make_designation(
            self.user,
            scopes=[("CENTRO", self.clinica_a), ("TIPO_CENTRO", "HOSPITAL")],
        )
        self.assertTrue(self._can(self.clinica_a))
        self.assertTrue(self._can(self.hospital))
        self.assertFalse(self._can(self.clinica_b))

    def test_s11_global_vigente_cubre_cualquier_centro(self):
        make_designation(self.user, end=HOY + timedelta(days=10), scopes=[("GLOBAL", None)])
        for centro in (self.clinica_a, self.clinica_b, self.hospital):
            self.assertTrue(self._can(centro))

    def test_global_sin_fecha_fin_no_habilita(self):
        make_designation(self.user, end=None, scopes=[("GLOBAL", None)])
        self.assertFalse(self._can(self.clinica_a))

    def test_prioriza_el_alcance_mas_especifico(self):
        make_designation(
            self.user,
            end=HOY + timedelta(days=5),
            scopes=[("GLOBAL", None), ("TIPO_CENTRO", "CLINICA"), ("CENTRO", self.clinica_a)],
        )
        self.assertEqual(self._can(self.clinica_a).alcance_aplicado, "CENTRO")
        self.assertEqual(self._can(self.clinica_b).alcance_aplicado, "TIPO_CENTRO")
        self.assertEqual(self._can(self.hospital).alcance_aplicado, "GLOBAL")

    # --- Vigencia ----------------------------------------------------------
    def test_s6_fecha_fin_ayer_deniega(self):
        make_designation(self.user, start=HOY - timedelta(days=30), end=HOY - timedelta(days=1),
                         scopes=[("CENTRO", self.clinica_a)])
        self.assertFalse(self._can(self.clinica_a))

    def test_s7_fecha_inicio_manana_deniega(self):
        make_designation(self.user, start=HOY + timedelta(days=1), scopes=[("CENTRO", self.clinica_a)])
        self.assertFalse(self._can(self.clinica_a))

    def test_s8_limites_inclusivos(self):
        make_designation(self.user, start=HOY, end=HOY, scopes=[("CENTRO", self.clinica_a)])
        self.assertTrue(self._can(self.clinica_a, fecha=HOY))
        self.assertFalse(self._can(self.clinica_a, fecha=HOY - timedelta(days=1)))
        self.assertFalse(self._can(self.clinica_a, fecha=HOY + timedelta(days=1)))

    def test_designacion_inactiva_o_eliminada_deniega(self):
        d = make_designation(self.user, scopes=[("CENTRO", self.clinica_a)])
        self.assertTrue(self._can(self.clinica_a))
        d.is_active = False
        d.save(update_fields=["is_active"])
        self.assertFalse(self._can(self.clinica_a))

    def test_item_de_alcance_dado_de_baja_deniega(self):
        d = make_designation(self.user)
        scope = add_scope(d, "CENTRO", self.clinica_a)
        self.assertTrue(self._can(self.clinica_a))
        scope.is_active = False
        scope.save(update_fields=["is_active"])
        self.assertFalse(self._can(self.clinica_a))

    # --- Tipo / adscripcion / bordes --------------------------------------
    def test_s13_designacion_de_otro_tipo_no_habilita(self):
        otro = get_tipo("ZZ", "Otro tipo")
        make_designation(self.user, otro, scopes=[("CENTRO", self.clinica_a)])
        self.assertFalse(self._can(self.clinica_a, tipo=TIPO_CANCELAR_NOTA))
        self.assertTrue(self._can(self.clinica_a, tipo="ZZ"))

    def test_s12_adscripcion_se_ignora(self):
        # El usuario esta adscrito a la clinica A pero la designacion es solo B.
        detalle = self.user.detalle
        detalle.id_centro_atencion = self.clinica_a
        detalle.save()
        make_designation(self.user, scopes=[("CENTRO", self.clinica_b)])
        self.assertFalse(self._can(self.clinica_a))
        self.assertTrue(self._can(self.clinica_b))
        detalle.refresh_from_db()
        self.assertEqual(detalle.id_centro_atencion_id, self.clinica_a.id)  # intacta

    def test_otro_usuario_no_hereda_la_designacion(self):
        make_designation(self.user, scopes=[("CENTRO", self.clinica_a)])
        self.assertFalse(self._can(self.clinica_a, user=make_user()))

    def test_centro_inexistente_deniega(self):
        make_designation(self.user, end=HOY + timedelta(days=5), scopes=[("GLOBAL", None)])
        decision = puede_autorizar(self.user.id_usuario, TIPO_CANCELAR_NOTA, 999999, HOY)
        self.assertFalse(decision)
        self.assertEqual(decision.motivo, "CENTRO_NO_ENCONTRADO")

    def test_decision_se_comporta_como_bool_y_expone_designacion(self):
        d = make_designation(self.user, scopes=[("CENTRO", self.clinica_a)])
        decision = self._can(self.clinica_a)
        self.assertIs(bool(decision), True)
        self.assertEqual(decision.designacion_id, d.id)
