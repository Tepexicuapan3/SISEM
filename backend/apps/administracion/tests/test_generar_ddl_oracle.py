"""
generar_ddl_oracle: estructura del Oracle de SERMED para una copia de
pruebas, solo con SELECT al diccionario. Oracle no existe en tests: un
cursor falso responde las consultas al diccionario de datos.
"""
import os
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.administracion.services import oracle_ddl_service as ddl
from apps.administracion.services.oracle_ddl_service import Columna, Esquema, Indice, Restriccion, Tabla

# Diccionario simulado: SERMED tiene CAT_EMPLEADOS y CAT_FAMILIAR; un sinonimo
# privado DNT_LICENCIAS_MEDICAS apunta a RH.LICENCIAS.
def _vistas(**vistas):
    """Filas de ALL_TAB_COLUMNS (owner SYS) que describen las vistas del diccionario."""
    return [{"table_name": v, "column_name": c} for v, cols in vistas.items() for c in cols]


# Diccionario de 11g+: todas las columnas que el comando sabe aprovechar.
VISTAS_MODERNAS = _vistas(
    ALL_TABLES=["TABLE_NAME", "DROPPED"],
    ALL_TAB_COLS=["COLUMN_NAME", "HIDDEN_COLUMN", "VIRTUAL_COLUMN"],
    ALL_CONSTRAINTS=["CONSTRAINT_NAME", "INDEX_NAME"],
    ALL_MVIEWS=["MVIEW_NAME"],
    ALL_EXTERNAL_TABLES=["TABLE_NAME"],
)
# Como el Oracle de SERMED (anterior a 10g): sin DROPPED, sin VIRTUAL_COLUMN
# y sin ALL_CONSTRAINTS.INDEX_NAME.
VISTAS_9I = _vistas(
    ALL_TABLES=["TABLE_NAME"],
    ALL_TAB_COLS=["COLUMN_NAME", "HIDDEN_COLUMN"],
    ALL_CONSTRAINTS=["CONSTRAINT_NAME"],
    ALL_MVIEWS=["MVIEW_NAME"],
)

DICCIONARIO = {
    # Primero: la deteccion de version tambien lee all_tab_columns.
    "owner = 'SYS'": VISTAS_MODERNAS,
    "FROM all_tables t": [
        {"owner": "SERMED", "table_name": "CAT_EMPLEADOS", "temporary": "N", "duration": None},
        {"owner": "SERMED", "table_name": "CAT_FAMILIAR", "temporary": "N", "duration": None},
        {"owner": "SERMED", "table_name": "TMP_CARGA", "temporary": "Y", "duration": "SYS$SESSION"},
    ],
    "FROM user_synonyms": [
        {"synonym_name": "DNT_LICENCIAS_MEDICAS", "table_owner": "RH", "table_name": "LICENCIAS",
         "temporary": "N", "duration": None},
        # Apunta a una tabla que ya se copia: no se duplica.
        {"synonym_name": "EMPLEADOS", "table_owner": "SERMED", "table_name": "CAT_EMPLEADOS",
         "temporary": "N", "duration": None},
    ],
    "FROM all_tab_comments": [
        {"owner": "SERMED", "table_name": "CAT_EMPLEADOS", "comments": "Titulares de Capital Humano"},
    ],
    "FROM all_tab_cols": [
        {"owner": "SERMED", "table_name": "CAT_EMPLEADOS", "column_name": "NO_EXP", "data_type": "VARCHAR2",
         "data_type_owner": None, "data_length": 20, "data_precision": None, "data_scale": None,
         "char_length": 20, "char_used": "B", "nullable": "N", "data_default": None, "virtual_column": "NO"},
        {"owner": "SERMED", "table_name": "CAT_EMPLEADOS", "column_name": "FEC_VIG", "data_type": "DATE",
         "data_type_owner": None, "data_length": 7, "data_precision": None, "data_scale": None,
         "char_length": 0, "char_used": None, "nullable": "Y", "data_default": "SYSDATE\n",
         "virtual_column": "NO"},
        {"owner": "SERMED", "table_name": "CAT_FAMILIAR", "column_name": "PK_NUM", "data_type": "NUMBER",
         "data_type_owner": None, "data_length": 22, "data_precision": 10, "data_scale": 0,
         "char_length": 0, "char_used": None, "nullable": "N", "data_default": None, "virtual_column": "NO"},
        {"owner": "SERMED", "table_name": "CAT_FAMILIAR", "column_name": "NO_EXPF", "data_type": "VARCHAR2",
         "data_type_owner": None, "data_length": 20, "data_precision": None, "data_scale": None,
         "char_length": 20, "char_used": "B", "nullable": "Y", "data_default": None, "virtual_column": "NO"},
        {"owner": "SERMED", "table_name": "TMP_CARGA", "column_name": "ID", "data_type": "NUMBER",
         "data_type_owner": None, "data_length": 22, "data_precision": None, "data_scale": None,
         "char_length": 0, "char_used": None, "nullable": "Y", "data_default": None, "virtual_column": "NO"},
        {"owner": "RH", "table_name": "LICENCIAS", "column_name": "NO_FOLIO", "data_type": "VARCHAR2",
         "data_type_owner": None, "data_length": 20, "data_precision": None, "data_scale": None,
         "char_length": 20, "char_used": "C", "nullable": "N", "data_default": None, "virtual_column": "NO"},
        # Tabla de RH que no se copia: sus columnas se ignoran.
        {"owner": "RH", "table_name": "NOMINA", "column_name": "SUELDO", "data_type": "NUMBER",
         "data_type_owner": None, "data_length": 22, "data_precision": 12, "data_scale": 2,
         "char_length": 0, "char_used": None, "nullable": "Y", "data_default": None, "virtual_column": "NO"},
    ],
    "FROM all_col_comments": [
        {"owner": "SERMED", "table_name": "CAT_EMPLEADOS", "column_name": "FEC_VIG", "comments": "Vigencia d'alta"},
    ],
    "FROM all_cons_columns": [
        {"owner": "SERMED", "constraint_name": "PK_CAT_EMPLEADOS", "column_name": "NO_EXP"},
        {"owner": "SERMED", "constraint_name": "PK_CAT_FAMILIAR", "column_name": "PK_NUM"},
        {"owner": "SERMED", "constraint_name": "FK_FAM_EMP", "column_name": "NO_EXPF"},
        {"owner": "SERMED", "constraint_name": "FK_FAM_NOMINA", "column_name": "NO_EXPF"},
        {"owner": "SERMED", "constraint_name": "SYS_C0011", "column_name": "NO_EXP"},
        {"owner": "SERMED", "constraint_name": "CK_FAM_PK_POSITIVO", "column_name": "PK_NUM"},
        {"owner": "RH", "constraint_name": "PK_LICENCIAS", "column_name": "NO_FOLIO"},
        {"owner": "RH", "constraint_name": "PK_NOMINA", "column_name": "SUELDO"},
    ],
    "FROM all_constraints": [
        {"owner": "SERMED", "table_name": "CAT_EMPLEADOS", "constraint_name": "PK_CAT_EMPLEADOS",
         "constraint_type": "P", "r_owner": None, "r_constraint_name": None, "delete_rule": None,
         "search_condition": None, "generated": "USER NAME", "status": "ENABLED",
         "index_name": "PK_CAT_EMPLEADOS"},
        {"owner": "SERMED", "table_name": "CAT_EMPLEADOS", "constraint_name": "SYS_C0011",
         "constraint_type": "C", "r_owner": None, "r_constraint_name": None, "delete_rule": None,
         "search_condition": '"NO_EXP" IS NOT NULL', "generated": "GENERATED NAME", "status": "ENABLED",
         "index_name": None},
        {"owner": "SERMED", "table_name": "CAT_FAMILIAR", "constraint_name": "PK_CAT_FAMILIAR",
         "constraint_type": "P", "r_owner": None, "r_constraint_name": None, "delete_rule": None,
         "search_condition": None, "generated": "USER NAME", "status": "ENABLED",
         "index_name": "PK_CAT_FAMILIAR"},
        {"owner": "SERMED", "table_name": "CAT_FAMILIAR", "constraint_name": "FK_FAM_EMP",
         "constraint_type": "R", "r_owner": "SERMED", "r_constraint_name": "PK_CAT_EMPLEADOS",
         "delete_rule": "CASCADE", "search_condition": None, "generated": "USER NAME",
         "status": "ENABLED", "index_name": None},
        {"owner": "SERMED", "table_name": "CAT_FAMILIAR", "constraint_name": "FK_FAM_NOMINA",
         "constraint_type": "R", "r_owner": "RH", "r_constraint_name": "PK_NOMINA",
         "delete_rule": "NO ACTION", "search_condition": None, "generated": "USER NAME",
         "status": "DISABLED", "index_name": None},
        {"owner": "SERMED", "table_name": "CAT_FAMILIAR", "constraint_name": "CK_FAM_PK_POSITIVO",
         "constraint_type": "C", "r_owner": None, "r_constraint_name": None, "delete_rule": None,
         "search_condition": "PK_NUM > 0", "generated": "USER NAME", "status": "ENABLED",
         "index_name": None},
        {"owner": "RH", "table_name": "LICENCIAS", "constraint_name": "PK_LICENCIAS",
         "constraint_type": "P", "r_owner": None, "r_constraint_name": None, "delete_rule": None,
         "search_condition": None, "generated": "USER NAME", "status": "ENABLED",
         "index_name": "PK_LICENCIAS"},
        {"owner": "RH", "table_name": "NOMINA", "constraint_name": "PK_NOMINA",
         "constraint_type": "P", "r_owner": None, "r_constraint_name": None, "delete_rule": None,
         "search_condition": None, "generated": "USER NAME", "status": "ENABLED",
         "index_name": "PK_NOMINA"},
    ],
    "FROM all_ind_columns": [
        {"owner": "SERMED", "index_owner": "SERMED", "index_name": "PK_CAT_EMPLEADOS", "column_name": "NO_EXP", "descend": "ASC"},
        {"owner": "SERMED", "index_owner": "SERMED", "index_name": "IX_FAM_EXP", "column_name": "NO_EXPF", "descend": "ASC"},
        {"owner": "SERMED", "index_owner": "SERMED", "index_name": "IX_FAM_EXP", "column_name": "PK_NUM", "descend": "DESC"},
    ],
    "FROM all_indexes": [
        {"owner": "SERMED", "index_name": "PK_CAT_EMPLEADOS", "table_name": "CAT_EMPLEADOS",
         "uniqueness": "UNIQUE", "index_type": "NORMAL"},
        {"owner": "SERMED", "index_name": "IX_FAM_EXP", "table_name": "CAT_FAMILIAR",
         "uniqueness": "NONUNIQUE", "index_type": "NORMAL"},
        {"owner": "SERMED", "index_name": "IX_FAM_UPPER", "table_name": "CAT_FAMILIAR",
         "uniqueness": "NONUNIQUE", "index_type": "FUNCTION-BASED NORMAL"},
    ],
    "FROM all_objects": [
        {"owner": "SERMED", "object_type": "SEQUENCE", "total": 3},
        {"owner": "SERMED", "object_type": "VIEW", "total": 2},
    ],
}


# DEFAULT_LENGTH: lo unico que la consulta en lote sabe del DEFAULT (LONG).
for _fila in DICCIONARIO["FROM all_tab_cols"]:
    _fila["default_length"] = len(_fila["data_default"]) if _fila["data_default"] else 0
# Antes de 9i (o sin visibilidad de ALL_TAB_COLS) las columnas salen de aqui.
DICCIONARIO["FROM all_tab_columns"] = DICCIONARIO["FROM all_tab_cols"]

ORA_03149 = "ORA-03149: Invalid Oracle error code"


class CursorDiccionario:
    """Responde por la tabla del diccionario que aparece en el SQL y filtra
    por owner (primer parametro) cuando la consulta lo recibe. Con
    ``fallar_long`` simula el ORA-03149 del Oracle de SERMED al leer LONG."""

    def __init__(self, vistas=None, fallar_long=False):
        self.description = None
        self._filas = []
        self.arraysize = 100
        self.sql = []
        self._vistas = VISTAS_MODERNAS if vistas is None else vistas
        self._fallar_long = fallar_long

    def _long(self, columna, filas, coincide):
        if self._fallar_long:
            raise RuntimeError(ORA_03149)
        self.description = [(columna.upper(),)]
        self._filas = [(f[columna],) for f in filas if coincide(f)][:1]

    def execute(self, sql, params=()):
        self.sql.append(sql)
        if "SELECT data_default FROM" in sql:
            owner, tabla, columna = params
            return self._long("data_default", DICCIONARIO["FROM all_tab_cols"], lambda f: (
                f["owner"], f["table_name"], f["column_name"]) == (owner, tabla, columna))
        if "SELECT search_condition FROM" in sql:
            owner, nombre = params
            return self._long("search_condition", DICCIONARIO["FROM all_constraints"], lambda f: (
                f["owner"], f["constraint_name"]) == (owner, nombre))
        if "SELECT USER FROM dual" in sql:
            self.description = [("USER",)]
            self._filas = [("SERMED",)]
            return
        if "product_component_version" in sql:
            self.description = [("VERSION",)]
            self._filas = [("9.2.0.8.0",)]
            return
        clave = next(k for k in DICCIONARIO if k in sql)
        filas = self._vistas if clave == "owner = 'SYS'" else DICCIONARIO[clave]
        if params:
            filas = [f for f in filas if f.get("owner", params[0]) == params[0]]
        columnas = [k for k in (filas[0] if filas else {}) if k != "owner" or "SELECT owner" in sql]
        if not columnas:
            columnas = ["vacio"]
        self.description = [(c.upper(),) for c in columnas]
        self._filas = [tuple(f.get(c) for c in columnas) for f in filas]

    def fetchall(self):
        return list(self._filas)

    def fetchone(self):
        return self._filas[0]

    def close(self):
        pass


class ConexionDiccionario:
    def __init__(self, vistas=None, fallar_long=False):
        self.cursores = []
        self._vistas = vistas
        self._fallar_long = fallar_long

    def cursor(self):
        cursor = CursorDiccionario(self._vistas, self._fallar_long)
        self.cursores.append(cursor)
        return cursor

    def close(self):
        pass

    def sql_ejecutado(self):
        return [s for c in self.cursores for s in c.sql]


def _script(vistas=None, **kw):
    esquema = ddl.leer_esquema(ConexionDiccionario(vistas), ["SERMED"])
    return esquema, ddl.generar_script(esquema, encabezado="-- prueba", **kw)


class VersionesDeOracleTests(SimpleTestCase):
    """El Oracle de SERMED es anterior a 10g: ORA-00904 "T"."DROPPED" en la
    primera corrida real. Las consultas se arman con lo que el diccionario
    tiene."""

    def _sql(self, vistas):
        conn = ConexionDiccionario(vistas)
        ddl.leer_esquema(conn, ["SERMED"])
        return "\n".join(conn.sql_ejecutado())

    def test_9i_no_usa_columnas_que_no_existen(self):
        sql = self._sql(VISTAS_9I)
        self.assertNotIn("dropped", sql)
        self.assertNotIn(" virtual_column", sql.replace("'NO' AS virtual_column", ""))
        self.assertIn("NULL AS index_name", sql)
        self.assertNotIn("all_external_tables", sql)
        self.assertIn("NOT LIKE 'BIN$%'", sql)

    def test_moderno_aprovecha_las_columnas_nuevas(self):
        sql = self._sql(VISTAS_MODERNAS)
        self.assertIn("t.dropped = 'NO'", sql)
        self.assertIn("all_tab_cols", sql)
        self.assertIn("virtual_column", sql)
        self.assertNotIn("NULL AS index_name", sql)

    def test_diccionario_vacio_usa_lo_minimo(self):
        sql = self._sql([])
        self.assertNotIn("all_tab_cols", sql)
        self.assertNotIn("all_mviews", sql)
        self.assertNotIn("hidden_column", sql)

    def test_9i_genera_el_mismo_script_sin_repetir_el_indice_de_la_llave(self):
        _, moderno = _script(VISTAS_MODERNAS)
        _, viejo = _script(VISTAS_9I)
        self.assertEqual(moderno, viejo)
        self.assertNotIn('INDEX "PK_CAT_EMPLEADOS"', viejo)

    def test_sin_join_ansi(self):
        self.assertNotIn(" JOIN ", self._sql(VISTAS_9I).upper())


class ColumnasLongTests(SimpleTestCase):
    """DATA_DEFAULT y SEARCH_CONDITION son LONG: traerlos en lote dio
    ORA-03149 contra el Oracle de SERMED. Se leen de a una fila y solo
    cuando hacen falta."""

    def test_ninguna_consulta_en_lote_pide_columnas_long(self):
        conn = ConexionDiccionario(VISTAS_9I)
        ddl.leer_esquema(conn, ["SERMED"])
        for sql in conn.sql_ejecutado():
            if "data_default" in sql or "search_condition" in sql:
                # Solo las lecturas puntuales, filtradas hasta una fila.
                self.assertTrue("column_name = :3" in sql or "constraint_name = :2" in sql, sql)

    def test_lee_defaults_y_checks_de_usuario_de_a_uno(self):
        conn = ConexionDiccionario(VISTAS_9I)
        esquema = ddl.leer_esquema(conn, ["SERMED"])
        script = ddl.generar_script(esquema, encabezado="-- prueba")
        self.assertIn('"FEC_VIG" DATE DEFAULT SYSDATE', script)
        self.assertIn('ALTER TABLE "CAT_FAMILIAR" ADD CONSTRAINT "CK_FAM_PK_POSITIVO" CHECK (PK_NUM > 0);', script)
        lecturas = [s for s in conn.sql_ejecutado() if "SELECT data_default" in s or "SELECT search_condition" in s]
        # 1 DEFAULT (FEC_VIG) + 1 CHECK de usuario: el NOT NULL de sistema no se lee.
        self.assertEqual(len(lecturas), 2)
        self.assertEqual(esquema.avisos, [])

    def test_un_long_ilegible_no_detiene_el_script_y_queda_como_aviso(self):
        esquema = ddl.leer_esquema(ConexionDiccionario(VISTAS_9I, fallar_long=True), ["SERMED"])
        script = ddl.generar_script(esquema, encabezado="-- prueba")

        self.assertIn('"FEC_VIG" DATE\n', script)
        self.assertNotIn("CK_FAM_PK_POSITIVO\" CHECK", script)
        self.assertEqual(len(esquema.avisos), 2)
        self.assertIn("-- ===== Avisos: revisar a mano (2) =====", script)
        self.assertIn("CAT_EMPLEADOS.FEC_VIG: no se pudo leer su DEFAULT (ORA-03149", script)
        self.assertIn("CHECK CK_FAM_PK_POSITIVO omitido", script)


class LeerEsquemaTests(SimpleTestCase):
    def test_solo_hace_select(self):
        conn = ConexionDiccionario()
        ddl.leer_esquema(conn, ["SERMED"])
        for sql in (s for c in conn.cursores for s in c.sql):
            self.assertTrue(sql.lstrip().upper().startswith("SELECT"), sql)

    def test_incluye_tablas_propias_y_las_de_sinonimos(self):
        esquema, _ = _script()
        self.assertEqual(
            {t.destino for t in esquema.tablas.values()},
            {"CAT_EMPLEADOS", "CAT_FAMILIAR", "TMP_CARGA", "DNT_LICENCIAS_MEDICAS"},
        )
        self.assertEqual(esquema.sinonimos, [("DNT_LICENCIAS_MEDICAS", "RH", "LICENCIAS")])
        self.assertNotIn(("RH", "NOMINA"), esquema.tablas)

    def test_sin_sinonimos(self):
        esquema = ddl.leer_esquema(ConexionDiccionario(), ["SERMED"], incluir_sinonimos=False)
        self.assertNotIn(("RH", "LICENCIAS"), esquema.tablas)

    def test_cuenta_lo_que_no_se_copia(self):
        esquema, script = _script()
        self.assertEqual(esquema.no_copiados, {"SEQUENCE": 3, "VIEW": 2})
        self.assertIn("--   SEQUENCE: 3", script)


class GenerarScriptTests(SimpleTestCase):
    def test_tabla_con_tipos_default_not_null_y_comentarios(self):
        _, script = _script()
        self.assertIn('CREATE TABLE "CAT_EMPLEADOS" (\n'
                      '  "NO_EXP" VARCHAR2(20 BYTE) NOT NULL,\n'
                      '  "FEC_VIG" DATE DEFAULT SYSDATE\n'
                      ');', script)
        self.assertIn('COMMENT ON TABLE "CAT_EMPLEADOS" IS \'Titulares de Capital Humano\';', script)
        self.assertIn('COMMENT ON COLUMN "CAT_EMPLEADOS"."FEC_VIG" IS \'Vigencia d\'\'alta\';', script)
        self.assertIn('"PK_NUM" NUMBER(10) NOT NULL', script)

    def test_tabla_por_sinonimo_se_crea_con_el_nombre_del_sinonimo(self):
        _, script = _script()
        self.assertIn('CREATE TABLE "DNT_LICENCIAS_MEDICAS" (\n  "NO_FOLIO" VARCHAR2(20 CHAR) NOT NULL\n);', script)
        self.assertIn('ALTER TABLE "DNT_LICENCIAS_MEDICAS" ADD CONSTRAINT "PK_LICENCIAS" PRIMARY KEY ("NO_FOLIO");', script)
        self.assertNotIn("NOMINA\" (", script)

    def test_temporal_global(self):
        _, script = _script()
        self.assertIn('CREATE GLOBAL TEMPORARY TABLE "TMP_CARGA" (\n  "ID" NUMBER\n) ON COMMIT PRESERVE ROWS;', script)

    def test_not_null_de_sistema_no_se_repite_como_check(self):
        _, script = _script()
        self.assertNotIn("IS NOT NULL", script)

    def test_foraneas_al_final_y_las_externas_comentadas(self):
        _, script = _script()
        fk = 'ALTER TABLE "CAT_FAMILIAR" ADD CONSTRAINT "FK_FAM_EMP" FOREIGN KEY ("NO_EXPF") ' \
             'REFERENCES "CAT_EMPLEADOS" ("NO_EXP") ON DELETE CASCADE;'
        self.assertIn(fk, script)
        self.assertGreater(script.index(fk), script.index("-- ===== 4. Indices"))
        self.assertIn('-- "CAT_FAMILIAR"."FK_FAM_NOMINA": referencia a RH.PK_NOMINA, que no esta en la copia.', script)

    def test_indices_sin_los_de_llaves_y_con_funcionales_comentados(self):
        _, script = _script()
        self.assertIn('CREATE INDEX "IX_FAM_EXP" ON "CAT_FAMILIAR" ("NO_EXPF", "PK_NUM" DESC);', script)
        self.assertNotIn('INDEX "PK_CAT_EMPLEADOS"', script)
        self.assertIn('-- Indice "IX_FAM_UPPER" (FUNCTION-BASED NORMAL)', script)

    def test_opciones_sin_indices_ni_foraneas(self):
        _, script = _script(incluir_indices=False, incluir_foraneas=False)
        self.assertNotIn("4. Indices", script)
        self.assertNotIn("FOREIGN KEY", script)

    def test_tipos(self):
        def tipo(**kw):
            return ddl.tipo_sql(Columna(nombre="X", **kw))

        self.assertEqual(tipo(tipo="NUMBER", precision=12, escala=2), "NUMBER(12,2)")
        self.assertEqual(tipo(tipo="NUMBER", escala=0), "NUMBER(*,0)")
        self.assertEqual(tipo(tipo="NUMBER"), "NUMBER")
        self.assertEqual(tipo(tipo="CHAR", char_length=1, char_used="B"), "CHAR(1 BYTE)")
        self.assertEqual(tipo(tipo="NVARCHAR2", char_length=50), "NVARCHAR2(50)")
        self.assertEqual(tipo(tipo="RAW", longitud=16), "RAW(16)")
        self.assertEqual(tipo(tipo="TIMESTAMP(6)"), "TIMESTAMP(6)")
        self.assertEqual(tipo(tipo="BLOB"), "BLOB")
        self.assertIsNone(tipo(tipo="T_DIRECCION", tipo_owner="SERMED"))

    def test_columna_de_tipo_de_usuario_queda_comentada_sin_romper_comas(self):
        esquema = Esquema(owners=["S"])
        esquema.tablas[("S", "T")] = Tabla(owner="S", nombre="T", destino="T", columnas=[
            Columna(nombre="A", tipo="NUMBER"),
            Columna(nombre="B", tipo="T_DIR", tipo_owner="S"),
        ])
        sql = ddl.render_tabla(esquema.tablas[("S", "T")])
        self.assertIn('  "A" NUMBER\n  -- "B": tipo de usuario S.T_DIR no copiado\n);', sql)

    def test_restriccion_deshabilitada_y_nombre_de_sistema(self):
        esquema = Esquema(owners=["S"])
        esquema.tablas[("S", "T")] = Tabla(owner="S", nombre="T", destino="T")
        r = Restriccion(owner="S", tabla="T", nombre="SYS_C1", tipo="U", columnas=["A"],
                        nombre_de_sistema=True, habilitada=False)
        self.assertEqual(ddl.render_restriccion(r, esquema, {}), 'ALTER TABLE "T" ADD UNIQUE ("A") DISABLE;')
        indice = Indice(owner="S", nombre="IX", tabla_owner="S", tabla="T", unico=False,
                        tipo="NORMAL/REV", columnas=[("A", False)])
        self.assertEqual(ddl.render_indice(indice, esquema), 'CREATE INDEX "IX" ON "T" ("A") REVERSE;')


class ComandoTests(SimpleTestCase):
    def test_escribe_el_script_y_cierra_la_conexion(self):
        conn = ConexionDiccionario()
        conn.close = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "copia.sql")
            out = StringIO()
            with mock.patch(
                "apps.administracion.management.commands.generar_ddl_oracle.obtener_conexion_oracle",
                return_value=conn,
            ):
                call_command("generar_ddl_oracle", "--output", ruta, stdout=out)
            with open(ruta, encoding="utf-8") as fh:
                script = fh.read()

        conn.close.assert_called_once()
        self.assertIn("NO EJECUTAR EN PRODUCCION", script)
        self.assertIn('CREATE TABLE "CAT_EMPLEADOS"', script)
        self.assertIn("Tablas: 4 (por sinonimo: 1)", out.getvalue())
