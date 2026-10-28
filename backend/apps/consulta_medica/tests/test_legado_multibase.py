"""
Plan identidad del paciente, bloque D: el legado vive en varias bases
(dbclinicas actual y las anuales dbclinicas2015...dbclinicas2024_a) y las
anuales traducen sus familiares con el cat_familiar de la base actual.
Los importadores masivos que usaban esto se retiraron en C7 (plan contraer
la llave vieja); el mapa de familiares se conserva.
"""
from unittest.mock import MagicMock

from django.test import TestCase

from apps.consulta_medica.services.legacy_family_map import LegacyFamilyMap


def _conexion(filas):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = filas
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn


class MapaFamiliaresOtraBaseTests(TestCase):
    """Las bases anuales traducen tp_paciente con el cat_familiar actual."""

    def test_lee_cat_familiar_de_la_base_indicada(self):
        conn = _conexion([{"cd_familiar": 9, "no_expf": 100, "pk_num": 48411}])
        LegacyFamilyMap.from_legacy_connection(conn, "dbclinicas")
        consulta = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
        self.assertIn("`dbclinicas`.cat_familiar", consulta)

    def test_sin_base_usa_la_misma_conexion(self):
        conn = _conexion([])
        LegacyFamilyMap.from_legacy_connection(conn)
        consulta = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
        self.assertEqual(consulta, "SELECT cd_familiar, no_expf, pk_num FROM cat_familiar")

    def test_rechaza_un_nombre_de_base_invalido(self):
        with self.assertRaises(ValueError):
            LegacyFamilyMap.from_legacy_connection(_conexion([]), "x; DROP TABLE y")
