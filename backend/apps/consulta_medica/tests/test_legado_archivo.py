"""
Copia del legado (alias "legado"): en tests no existe; la conexion se simula.
"""
from unittest import mock

from django.db import OperationalError
from django.test import SimpleTestCase, override_settings

from apps.consulta_medica.services import legado_archivo

CON_LEGADO = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
              "legado": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}


def _cursor(filas, columnas):
    cursor = mock.MagicMock()
    cursor.description = [(c,) for c in columnas]
    cursor.fetchall.return_value = filas
    conexion = mock.MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    return conexion, cursor


@override_settings(LEGADO_MOTOR="postgresql")
class LegadoArchivoTests(SimpleTestCase):
    def test_sin_configurar_no_esta_disponible(self):
        self.assertFalse(legado_archivo.disponible())
        with self.assertRaises(legado_archivo.LegadoNoDisponible):
            legado_archivo.consultar("SELECT 1")

    def test_tabla_valida_los_nombres(self):
        self.assertEqual(legado_archivo.tabla("legado_2015", "his_notas"), '"legado_2015"."his_notas"')
        for esquema, nombre in (("public", "his_notas"), ("legado_x;drop", "t"), ("legado_actual", "a b")):
            with self.assertRaises(ValueError):
                legado_archivo.tabla(esquema, nombre)

    @override_settings(DATABASES=CON_LEGADO)
    def test_consultar_devuelve_dicts(self):
        conexion, cursor = _cursor([("40041", 0)], ["no_exp", "tp_paciente"])
        with mock.patch.object(legado_archivo, "connections", {"legado": conexion}):
            filas = legado_archivo.consultar("SELECT no_exp, tp_paciente FROM t WHERE no_exp = %s", ["40041"])
        self.assertEqual(filas, [{"no_exp": "40041", "tp_paciente": 0}])
        cursor.execute.assert_called_once_with("SELECT no_exp, tp_paciente FROM t WHERE no_exp = %s", ["40041"])

    @override_settings(DATABASES=CON_LEGADO)
    def test_una_falla_de_la_copia_se_informa_como_no_disponible(self):
        conexion, cursor = _cursor([], [])
        cursor.execute.side_effect = OperationalError("connection refused")
        with mock.patch.object(legado_archivo, "connections", {"legado": conexion}):
            with self.assertRaises(legado_archivo.LegadoNoDisponible):
                legado_archivo.consultar("SELECT 1")

    @override_settings(DATABASES=CON_LEGADO)
    def test_esquemas_con_tabla_primero_la_actual_y_descarta_nombres_raros(self):
        filas = [("legado_2015",), ("legado_actual",), ("legado_2024_a",), ("legado_Raro",)]
        conexion, _ = _cursor(filas, ["table_schema"])
        with mock.patch.object(legado_archivo, "connections", {"legado": conexion}):
            self.assertEqual(legado_archivo.esquemas_con_tabla("his_notas"),
                             ["legado_actual", "legado_2024_a", "legado_2015"])


ESPEJO_MYSQL = {"host": "espejo", "port": 3306, "user": "lectura", "password": "x", "base_actual": "dbclinicas"}


@override_settings(LEGADO_MOTOR="mysql", LEGADO_MYSQL=ESPEJO_MYSQL)
class LegadoEspejoMysqlTests(SimpleTestCase):
    """Espejo MySQL del legado: mismos nombres logicos, traducidos a dbclinicas*."""

    def test_sin_host_no_esta_disponible(self):
        with override_settings(LEGADO_MYSQL={**ESPEJO_MYSQL, "host": ""}):
            self.assertFalse(legado_archivo.disponible())
        self.assertTrue(legado_archivo.disponible())

    def test_tabla_usa_la_base_fisica(self):
        self.assertEqual(legado_archivo.tabla("legado_actual", "his_notas"), "`dbclinicas`.`his_notas`")
        self.assertEqual(legado_archivo.tabla("legado_2024_a", "his_notas"), "`dbclinicas2024_a`.`his_notas`")
        with self.assertRaises(ValueError):
            legado_archivo.tabla("legado_x;drop", "t")

    def test_comparaciones_en_sintaxis_mysql(self):
        self.assertEqual(legado_archivo.texto("n.cd_medico"), "CAST(n.cd_medico AS CHAR)")
        # Sin envolver las columnas con indice: MySQL convierte el parametro y usa el indice.
        self.assertEqual(legado_archivo.sin_ceros("n.no_exp"), "n.no_exp")
        self.assertEqual(legado_archivo.valor_expediente("040041"), 40041)
        self.assertEqual(legado_archivo.clave("d.cd_snota"), "d.cd_snota")

    def test_esquemas_con_tabla_traduce_las_bases(self):
        filas = [{"esquema": "dbclinicas2015"}, {"esquema": "dbclinicas"},
                 {"esquema": "dbclinicas2024_a"}, {"esquema": "otra_base"}]
        with mock.patch.object(legado_archivo, "_consultar_mysql", return_value=filas):
            self.assertEqual(legado_archivo.esquemas_con_tabla("his_notas"),
                             ["legado_actual", "legado_2024_a", "legado_2015"])

    def test_solo_acepta_select(self):
        with self.assertRaises(ValueError):
            legado_archivo.consultar("DELETE FROM t")

    def test_abre_en_solo_lectura_y_devuelve_las_filas(self):
        cursor = mock.MagicMock()
        cursor.fetchall.return_value = [{"no_exp": "40041"}]
        conexion = mock.MagicMock()
        conexion.cursor.return_value.__enter__.return_value = cursor
        with mock.patch("pymysql.connect", return_value=conexion):
            filas = legado_archivo.consultar("SELECT no_exp FROM t WHERE no_exp = %s", ["40041"])
        self.assertEqual(filas, [{"no_exp": "40041"}])
        cursor.execute.assert_any_call("SET SESSION TRANSACTION READ ONLY")
        cursor.execute.assert_called_with("SELECT no_exp FROM t WHERE no_exp = %s", ["40041"])
        conexion.close.assert_called_once()

    def test_si_el_espejo_no_responde_se_informa_como_no_disponible(self):
        import pymysql

        with mock.patch("pymysql.connect", side_effect=pymysql.err.OperationalError(2003, "refused")):
            with self.assertRaises(legado_archivo.LegadoNoDisponible):
                legado_archivo.consultar("SELECT 1")
