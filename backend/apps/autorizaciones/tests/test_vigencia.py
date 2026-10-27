"""Estado de vigencia calculado (no se guarda): F1, plan autorizadores-medicos."""
from datetime import date

from django.test import SimpleTestCase

from apps.autorizaciones.domain.vigencia import EstadoVigencia, estado_vigencia

INICIO = date(2026, 1, 1)
FIN = date(2026, 12, 31)


class EstadoVigenciaTests(SimpleTestCase):
    def test_antes_del_inicio_esta_pendiente(self):
        self.assertEqual(estado_vigencia(INICIO, FIN, date(2025, 12, 31)), EstadoVigencia.PENDIENTE_INICIO)

    def test_dentro_del_periodo_esta_vigente(self):
        self.assertEqual(estado_vigencia(INICIO, FIN, date(2026, 6, 1)), EstadoVigencia.VIGENTE)

    def test_limites_inclusivos(self):
        self.assertEqual(estado_vigencia(INICIO, FIN, INICIO), EstadoVigencia.VIGENTE)
        self.assertNotEqual(estado_vigencia(INICIO, FIN, FIN), EstadoVigencia.VENCIDO)

    def test_dentro_de_los_dias_de_aviso_esta_por_vencer(self):
        self.assertEqual(
            estado_vigencia(INICIO, FIN, date(2026, 12, 16), dias_aviso=15), EstadoVigencia.POR_VENCER,
        )
        self.assertEqual(
            estado_vigencia(INICIO, FIN, date(2026, 12, 15), dias_aviso=15), EstadoVigencia.VIGENTE,
        )

    def test_despues_del_fin_esta_vencido(self):
        self.assertEqual(estado_vigencia(INICIO, FIN, date(2027, 1, 1)), EstadoVigencia.VENCIDO)

    def test_solo_vigente_y_por_vencer_habilitan(self):
        self.assertTrue(EstadoVigencia.VIGENTE.habilita)
        self.assertTrue(EstadoVigencia.POR_VENCER.habilita)
        self.assertFalse(EstadoVigencia.VENCIDO.habilita)
        self.assertFalse(EstadoVigencia.PENDIENTE_INICIO.habilita)
