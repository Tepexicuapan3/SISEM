"""
Regresion: ningun pk_num puede ser smallint. Los PK_NUM de SERMED pasan de
32 767 (p. ej. 48411) y en Postgres el guardado falla con "smallint out of
range". Le paso a rcp_visits (recepcion.0006) y despues a citas_medicas
(recepcion.0027). SQLite, donde corren los tests, no tiene ese limite: por
eso se revisa el tipo declarado en vez de intentar guardar.
"""
from django.apps import apps
from django.test import SimpleTestCase

TIPOS_CORTOS = {"SmallIntegerField", "PositiveSmallIntegerField", "SmallAutoField"}


class PkNumNoEsSmallintTests(SimpleTestCase):
    def test_ningun_modelo_declara_pk_num_como_smallint(self):
        cortos = [
            f"{modelo._meta.label}.{campo.name} ({campo.get_internal_type()})"
            for modelo in apps.get_models()
            for campo in modelo._meta.concrete_fields
            if campo.name == "pk_num" and campo.get_internal_type() in TIPOS_CORTOS
        ]
        self.assertEqual(cortos, [], "pk_num tiene que admitir PK_NUM de SERMED mayores a 32767")
