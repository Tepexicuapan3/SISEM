"""
Regla de clínica (``WRONG_CLINIC`` en citas, ``CLINICA_NO_CORRESPONDE`` en el
portal): la clave ``CD_CLINICA`` de SERMED se traduce al centro de SIRES con
la equivalencia de P-03 (``adscripcion_clinica_centro``). Sin equivalencia
activa se compara contra el id del centro, como antes.
"""

from django.test import TestCase

from apps.catalogos.models import CatCentroAtencion
from apps.recepcion.models import AdscripcionClinicaCentro
from apps.recepcion.services.clinica_paciente_service import centro_permitido, regla_de_clinica


class ReglaDeClinicaTests(TestCase):
    def setUp(self):
        self.centro_a = self._centro("Clínica A", "CL-A")
        self.centro_b = self._centro("Clínica B", "CL-B")

    def _centro(self, nombre, code):
        return CatCentroAtencion.objects.create(
            name=nombre, code=code, center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )

    def _equivalencia(self, clave, centro, *, activa=True):
        return AdscripcionClinicaCentro.objects.create(
            clave_clinica_sermed=clave, centro=centro, esta_activo=activa,
        )

    def test_usa_la_equivalencia_y_no_el_id_del_centro(self):
        # La clave SERMED coincide con el id de A, pero la equivalencia dice B.
        clave = str(self.centro_a.id)
        self._equivalencia(clave, self.centro_b)

        self.assertTrue(centro_permitido(clave, self.centro_b.id))
        self.assertFalse(centro_permitido(clave, self.centro_a.id))

    def test_clave_distinta_del_id_con_equivalencia(self):
        self._equivalencia("40", self.centro_a)

        self.assertTrue(centro_permitido("40", self.centro_a.id))
        self.assertFalse(centro_permitido("40", self.centro_b.id))

    def test_sin_equivalencia_compara_con_el_id_del_centro(self):
        clave = str(self.centro_a.id)

        self.assertTrue(centro_permitido(clave, self.centro_a.id))
        self.assertFalse(centro_permitido(clave, self.centro_b.id))

    def test_equivalencia_inactiva_no_cuenta(self):
        clave = str(self.centro_a.id)
        self._equivalencia(clave, self.centro_b, activa=False)

        self.assertTrue(centro_permitido(clave, self.centro_a.id))
        self.assertFalse(centro_permitido(clave, self.centro_b.id))

    def test_sin_dato_de_clinica_o_de_centro_no_bloquea(self):
        self.assertTrue(centro_permitido(None, self.centro_a.id))
        self.assertTrue(centro_permitido("40", None))

    def test_la_regla_se_resuelve_una_vez_para_muchos_centros(self):
        self._equivalencia("40", self.centro_a)

        with self.assertNumQueries(1):
            permite = regla_de_clinica("40")
        with self.assertNumQueries(0):
            resultados = [permite(c) for c in (self.centro_a.id, self.centro_b.id, None)]

        self.assertEqual(resultados, [True, False, True])
