"""
DDL (solo estructura, sin datos) de un esquema de Oracle, leido del
diccionario de datos con SELECT. Sirve para crear una copia de pruebas del
Oracle de SERMED sin sacar de produccion ningun dato personal.

SOLO LECTURA sobre Oracle (regla del proyecto): aqui no se ejecuta ningun
CREATE/ALTER/INSERT; se devuelve texto. El .sql lo corre una persona en la
COPIA, nunca en produccion.

Se copian: tablas (incluidas las temporales globales), columnas con tipo,
default, NOT NULL y columnas virtuales, comentarios, llaves primarias y
unicas, checks, indices normales/bitmap/reverse y llaves foraneas. Las
tablas a las que apuntan los sinonimos privados del usuario se crean con el
nombre del sinonimo: SIRES consulta "FROM cat_empleados" sin esquema.

No se copian (quedan listados al final del script): vistas, secuencias,
triggers, codigo PL/SQL, tipos, vistas materializadas, particiones (la tabla
se crea sin particionar) e indices basados en funciones.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

TIPOS_INDICE_COPIABLES = {"NORMAL", "BITMAP", "NORMAL/REV"}
OBJETOS_NO_COPIADOS = (
    "VIEW", "SEQUENCE", "TRIGGER", "PROCEDURE", "FUNCTION", "PACKAGE",
    "TYPE", "MATERIALIZED VIEW", "SYNONYM", "DATABASE LINK",
)
# Los NOT NULL de una columna Oracle los guarda tambien como CHECK con nombre
# de sistema: ya salen en la definicion de la columna.
_NOT_NULL_DE_SISTEMA = re.compile(r'^\s*"?[^"\s]+"?\s+IS\s+NOT\s+NULL\s*$', re.IGNORECASE)


def q(nombre: str) -> str:
    """Identificador entre comillas: conserva mayusculas/minusculas exactas."""
    return '"' + str(nombre).replace('"', '""') + '"'


def _literal(texto: str) -> str:
    return "'" + str(texto).replace("'", "''") + "'"


def _texto(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


@dataclass
class Columna:
    nombre: str
    tipo: str
    tipo_owner: str | None = None
    longitud: int | None = None
    precision: int | None = None
    escala: int | None = None
    char_length: int | None = None
    char_used: str | None = None
    nullable: bool = True
    default: str | None = None
    virtual: bool = False


@dataclass
class Tabla:
    owner: str
    nombre: str
    destino: str
    # SYS$SESSION / SYS$TRANSACTION en tablas temporales globales.
    duracion: str | None = None
    comentario: str | None = None
    columnas: list[Columna] = field(default_factory=list)
    comentarios_columnas: dict[str, str] = field(default_factory=dict)


@dataclass
class Restriccion:
    owner: str
    tabla: str
    nombre: str
    tipo: str                       # P, U, R, C
    columnas: list[str] = field(default_factory=list)
    ref_owner: str | None = None
    ref_nombre: str | None = None
    regla_borrado: str | None = None
    condicion: str | None = None
    nombre_de_sistema: bool = False
    habilitada: bool = True
    indice: str | None = None


@dataclass
class Indice:
    owner: str
    nombre: str
    tabla_owner: str
    tabla: str
    unico: bool
    tipo: str
    columnas: list[tuple[str, bool]] = field(default_factory=list)   # (columna, descendente)


@dataclass
class Esquema:
    owners: list[str]
    tablas: dict[tuple[str, str], Tabla] = field(default_factory=dict)
    restricciones: list[Restriccion] = field(default_factory=list)
    indices: list[Indice] = field(default_factory=list)
    no_copiados: dict[str, int] = field(default_factory=dict)
    # (sinonimo, owner real, tabla real) de las tablas traidas por sinonimo.
    sinonimos: list[tuple[str, str, str]] = field(default_factory=list)
    # Lo que no se pudo leer (p. ej. un DEFAULT LONG ilegible): va al final
    # del script para completarlo a mano.
    avisos: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Generacion de SQL (sin Oracle: se testea con datos en memoria)
# ──────────────────────────────────────────────────────────────

def tipo_sql(col: Columna) -> str | None:
    """Tipo de la columna en DDL. None si es un tipo de usuario que no se copia."""
    tipo = col.tipo
    if col.tipo_owner and col.tipo_owner not in ("SYS", "PUBLIC"):
        return None
    if tipo in ("VARCHAR2", "CHAR"):
        unidad = "CHAR" if col.char_used == "C" else "BYTE"
        return f"{tipo}({col.char_length or col.longitud} {unidad})"
    if tipo in ("NVARCHAR2", "NCHAR"):
        return f"{tipo}({col.char_length or col.longitud})"
    if tipo == "NUMBER":
        if col.precision is None:
            return "NUMBER" if col.escala is None else f"NUMBER(*,{col.escala})"
        return f"NUMBER({col.precision})" if not col.escala else f"NUMBER({col.precision},{col.escala})"
    if tipo == "FLOAT":
        return f"FLOAT({col.precision})" if col.precision else "FLOAT"
    if tipo in ("RAW", "UROWID"):
        return f"{tipo}({col.longitud})"
    # DATE, TIMESTAMP(n) [WITH ...], INTERVAL ..., CLOB, BLOB, NCLOB, LONG,
    # LONG RAW, BINARY_FLOAT/DOUBLE, ROWID, XMLTYPE: el nombre ya es el DDL.
    return tipo


def _definicion_columna(col: Columna) -> str:
    tipo = tipo_sql(col)
    if tipo is None:
        return f"  -- {q(col.nombre)}: tipo de usuario {col.tipo_owner}.{col.tipo} no copiado"
    if col.virtual and col.default:
        return f"  {q(col.nombre)} {tipo} GENERATED ALWAYS AS ({col.default}) VIRTUAL"
    partes = [f"  {q(col.nombre)} {tipo}"]
    if col.default:
        partes.append(f"DEFAULT {col.default}")
    if not col.nullable:
        partes.append("NOT NULL")
    return " ".join(partes)


def render_tabla(tabla: Tabla) -> str:
    definiciones = [_definicion_columna(c) for c in tabla.columnas]
    # Las columnas no copiadas van como comentario: no llevan coma.
    reales = [i for i, d in enumerate(definiciones) if not d.lstrip().startswith("--")]
    lineas = []
    for i, definicion in enumerate(definiciones):
        coma = "," if reales and i in reales and i != reales[-1] else ""
        lineas.append(definicion + coma)
    if tabla.duracion:
        cabecera = f"CREATE GLOBAL TEMPORARY TABLE {q(tabla.destino)} ("
        filas = "PRESERVE" if tabla.duracion == "SYS$SESSION" else "DELETE"
        cierre = f") ON COMMIT {filas} ROWS;"
    else:
        cabecera = f"CREATE TABLE {q(tabla.destino)} ("
        cierre = ");"
    sql = [cabecera, *lineas, cierre]
    if tabla.comentario:
        sql.append(f"COMMENT ON TABLE {q(tabla.destino)} IS {_literal(tabla.comentario)};")
    for columna, comentario in tabla.comentarios_columnas.items():
        sql.append(f"COMMENT ON COLUMN {q(tabla.destino)}.{q(columna)} IS {_literal(comentario)};")
    return "\n".join(sql)


def _nombre_restriccion(r: Restriccion) -> str:
    # Los nombres SYS_C... son de sistema: en la copia los genera Oracle.
    return "" if r.nombre_de_sistema else f"CONSTRAINT {q(r.nombre)} "


def _columnas(columnas) -> str:
    return ", ".join(q(c) for c in columnas)


def render_restriccion(r: Restriccion, esquema: Esquema,
                       por_nombre: dict[tuple[str, str], Restriccion]) -> str | None:
    """ALTER TABLE ... ADD ...; None si no hay nada que copiar (NOT NULL de sistema)."""
    tabla = esquema.tablas[(r.owner, r.tabla)]
    estado = "" if r.habilitada else " DISABLE"
    prefijo = f"ALTER TABLE {q(tabla.destino)} ADD {_nombre_restriccion(r)}"
    if r.tipo == "P":
        return f"{prefijo}PRIMARY KEY ({_columnas(r.columnas)}){estado};"
    if r.tipo == "U":
        return f"{prefijo}UNIQUE ({_columnas(r.columnas)}){estado};"
    if r.tipo == "C":
        if not r.condicion or (r.nombre_de_sistema and _NOT_NULL_DE_SISTEMA.match(r.condicion)):
            return None
        return f"{prefijo}CHECK ({r.condicion}){estado};"
    if r.tipo == "R":
        ref = por_nombre.get((r.ref_owner, r.ref_nombre))
        if ref is None or (ref.owner, ref.tabla) not in esquema.tablas:
            return (f"-- {q(tabla.destino)}.{q(r.nombre)}: referencia a {r.ref_owner}.{r.ref_nombre}, "
                    "que no esta en la copia.")
        destino_ref = esquema.tablas[(ref.owner, ref.tabla)].destino
        borrado = ""
        if r.regla_borrado == "CASCADE":
            borrado = " ON DELETE CASCADE"
        elif r.regla_borrado == "SET NULL":
            borrado = " ON DELETE SET NULL"
        return (f"{prefijo}FOREIGN KEY ({_columnas(r.columnas)}) "
                f"REFERENCES {q(destino_ref)} ({_columnas(ref.columnas)}){borrado}{estado};")
    return None


def render_indice(indice: Indice, esquema: Esquema) -> str:
    tabla = esquema.tablas[(indice.tabla_owner, indice.tabla)]
    if indice.tipo not in TIPOS_INDICE_COPIABLES:
        return f"-- Indice {q(indice.nombre)} ({indice.tipo}) sobre {q(tabla.destino)}: no copiado."
    clase = "UNIQUE " if indice.unico else ("BITMAP " if indice.tipo == "BITMAP" else "")
    columnas = ", ".join(q(c) + (" DESC" if desc else "") for c, desc in indice.columnas)
    reverso = " REVERSE" if indice.tipo == "NORMAL/REV" else ""
    return f"CREATE {clase}INDEX {q(indice.nombre)} ON {q(tabla.destino)} ({columnas}){reverso};"


def generar_script(esquema: Esquema, *, encabezado: str, incluir_indices: bool = True,
                   incluir_foraneas: bool = True, guardia: str | None = None) -> str:
    # Todas (tambien las de tablas no copiadas) para resolver foraneas; solo
    # las de tablas copiadas se escriben.
    por_nombre = {(r.owner, r.nombre): r for r in esquema.restricciones}
    tablas = sorted(esquema.tablas.values(), key=lambda t: t.destino)
    restricciones = sorted(
        copiables(esquema), key=lambda r: (esquema.tablas[(r.owner, r.tabla)].destino, r.nombre),
    )
    indices_de_restriccion = {(r.owner, r.indice) for r in restricciones if r.indice and r.tipo in "PU"}
    # Antes de 10g no hay ALL_CONSTRAINTS.INDEX_NAME: un indice con las mismas
    # columnas que una PK/UK de su tabla es el que la respalda. La llave crea
    # el suyo en la copia; repetirlo daria ORA-01408.
    columnas_de_llaves = {
        (r.owner, r.tabla, tuple(r.columnas)) for r in restricciones if r.tipo in "PU"
    }

    partes = [encabezado.rstrip(), ""]
    if guardia:
        partes += [guardia, ""]
    if esquema.sinonimos:
        partes.append("-- Tablas traidas por sinonimo (se crean con el nombre del sinonimo):")
        partes += [f"--   {s} -> {o}.{t}" for s, o, t in sorted(esquema.sinonimos)]
        partes.append("")

    partes.append(f"-- ===== 1. Tablas ({len(tablas)}) =====")
    for tabla in tablas:
        partes += [render_tabla(tabla), ""]

    def seccion(titulo, tipos):
        lineas = [render_restriccion(r, esquema, por_nombre) for r in restricciones if r.tipo in tipos]
        lineas = [l for l in lineas if l]
        partes.append(f"-- ===== {titulo} ({len(lineas)}) =====")
        partes.extend(lineas)
        partes.append("")

    seccion("2. Llaves primarias y unicas", "PU")
    seccion("3. Checks", "C")

    if incluir_indices:
        indices = [
            i for i in sorted(esquema.indices, key=lambda i: i.nombre)
            if (i.tabla_owner, i.tabla) in esquema.tablas
            and (i.owner, i.nombre) not in indices_de_restriccion
            and (i.tabla_owner, i.tabla, tuple(c for c, _ in i.columnas)) not in columnas_de_llaves
        ]
        partes.append(f"-- ===== 4. Indices ({len(indices)}) =====")
        partes += [render_indice(i, esquema) for i in indices]
        partes.append("")

    if incluir_foraneas:
        # Al final: dependen de que existan todas las tablas y sus llaves.
        seccion("5. Llaves foraneas", "R")

    if esquema.no_copiados:
        partes.append("-- ===== No copiado (crear a mano si las pruebas lo necesitan) =====")
        partes += [f"--   {tipo}: {n}" for tipo, n in sorted(esquema.no_copiados.items())]
        partes.append("")
    if esquema.avisos:
        partes.append(f"-- ===== Avisos: revisar a mano ({len(esquema.avisos)}) =====")
        partes += [f"--   {aviso}" for aviso in esquema.avisos]
    return "\n".join(partes).rstrip() + "\n"


# ──────────────────────────────────────────────────────────────
# Lectura del diccionario de Oracle (solo SELECT)
# ──────────────────────────────────────────────────────────────

def _filas(cursor, sql: str, params=()) -> list[dict]:
    cursor.execute(sql, params)
    nombres = [d[0].lower() for d in cursor.description]
    return [dict(zip(nombres, fila)) for fila in cursor.fetchall()]


def _leer_long(cursor, sql: str, params) -> tuple[str | None, str | None]:
    """
    Un valor LONG del diccionario (DATA_DEFAULT, SEARCH_CONDITION), de a una
    fila. Traer LONG en lote contra el Oracle de SERMED (anterior a 10g, con
    cliente 11.2) rompe el fetch con ORA-03149, asi que las consultas grandes
    nunca piden columnas LONG. Devuelve (valor, error): un valor ilegible no
    detiene el script, queda como aviso.
    """
    try:
        cursor.execute(sql, params)
        fila = cursor.fetchone()
        return (_texto(fila[0]) if fila else None), None
    except Exception as exc:
        return None, str(exc).splitlines()[0]


def usuario_actual(conn) -> str:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT USER FROM dual")
        return cursor.fetchone()[0]
    finally:
        cursor.close()


def version_oracle(conn) -> str | None:
    """Version del servidor, solo informativa (None si no hay permiso)."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT version FROM product_component_version WHERE product LIKE 'Oracle%'"
        )
        fila = cursor.fetchone()
        return fila[0] if fila else None
    except Exception:
        return None
    finally:
        cursor.close()


def identidad_base(conn) -> tuple[str, str]:
    """
    (DB_NAME, GLOBAL_NAME) de la base a la que se esta conectado: la de
    ORIGEN (produccion). Con eso el script se niega a correr ahi. Si no se
    puede leer, la excepcion sube: sin identidad no hay guardia, y sin
    guardia no se genera el script.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT SYS_CONTEXT('USERENV', 'DB_NAME'), (SELECT global_name FROM global_name) FROM dual"
        )
        db_name, global_name = cursor.fetchone()
    finally:
        cursor.close()
    db_name, global_name = _texto(db_name), _texto(global_name)
    if not db_name or not global_name:
        raise ValueError("Oracle no informo DB_NAME / GLOBAL_NAME de la base de origen.")
    return db_name.upper(), global_name.upper()


def guardia_produccion(db_name: str, global_name: str) -> str:
    """
    Primer bloque del script: si se ejecuta en la base de origen, aborta
    antes de crear nada. WHENEVER SQLERROR EXIT hace que SQL Developer (F5)
    y sqlplus corten el script completo ante ese error (y ante cualquier
    otro: el script no sigue a medias).
    """
    return "\n".join([
        "-- ===== 0. Guardia: este script NO puede correr en PRODUCCION =====",
        f"-- Base de origen (produccion): DB_NAME={db_name}, GLOBAL_NAME={global_name}.",
        "-- Si se ejecuta ahi, aborta antes del primer CREATE.",
        "WHENEVER SQLERROR EXIT SQL.SQLCODE",
        "DECLARE",
        "  v_db_name     VARCHAR2(200) := UPPER(SYS_CONTEXT('USERENV', 'DB_NAME'));",
        "  v_global_name VARCHAR2(4000);",
        "BEGIN",
        "  SELECT UPPER(global_name) INTO v_global_name FROM global_name;",
        f"  IF v_db_name = {_literal(db_name)} OR v_global_name = {_literal(global_name)} THEN",
        "    RAISE_APPLICATION_ERROR(-20001,",
        f"      'ALTO: esta es la base de PRODUCCION ({db_name}). '",
        "      || 'Este script solo se ejecuta en la COPIA DE PRUEBAS.');",
        "  END IF;",
        "END;",
        "/",
    ])


# Vistas del diccionario cuyas columnas cambian entre versiones de Oracle.
_VISTAS_VERSIONADAS = ("ALL_TABLES", "ALL_TAB_COLS", "ALL_CONSTRAINTS", "ALL_MVIEWS", "ALL_EXTERNAL_TABLES")


@dataclass(frozen=True)
class Diccionario:
    """
    Que ofrece el diccionario de ESTA version de Oracle. El de SERMED es
    anterior a 10g (no tiene ALL_TABLES.DROPPED): en vez de suponer una
    version, se pregunta que columnas existen y las consultas se arman con
    lo que hay. Un diccionario vacio = la version mas antigua posible.
    """
    columnas: dict[str, frozenset[str]]

    def tiene(self, vista: str, columna: str | None = None) -> bool:
        disponibles = self.columnas.get(vista)
        if disponibles is None:
            return False
        return columna is None or columna in disponibles


def leer_diccionario(cursor) -> Diccionario:
    vistas: dict[str, set[str]] = defaultdict(set)
    marcadores = ", ".join(f":{i + 1}" for i in range(len(_VISTAS_VERSIONADAS)))
    for f in _filas(cursor, f"""
        SELECT table_name, column_name FROM all_tab_columns
        WHERE owner = 'SYS' AND table_name IN ({marcadores})
    """, _VISTAS_VERSIONADAS):
        vistas[f["table_name"]].add(f["column_name"])
    return Diccionario({vista: frozenset(cols) for vista, cols in vistas.items()})


def leer_esquema(conn, owners: list[str], *, incluir_sinonimos: bool = True) -> Esquema:
    esquema = Esquema(owners=list(owners))
    cursor = conn.cursor()
    cursor.arraysize = 1000
    try:
        dic = leer_diccionario(cursor)
        # Papelera (10g+): por DROPPED si existe; los nombres BIN$ siempre.
        sin_papelera = "AND t.dropped = 'NO' " if dic.tiene("ALL_TABLES", "DROPPED") else ""
        sin_papelera += "AND t.table_name NOT LIKE 'BIN$%'"
        excluir_mviews = (
            "AND NOT EXISTS (SELECT 1 FROM all_mviews m "
            "WHERE m.owner = t.owner AND m.mview_name = t.table_name)"
            if dic.tiene("ALL_MVIEWS") else ""
        )
        excluir_externas = (
            "AND NOT EXISTS (SELECT 1 FROM all_external_tables e "
            "WHERE e.owner = t.owner AND e.table_name = t.table_name)"
            if dic.tiene("ALL_EXTERNAL_TABLES") else ""
        )

        # Tablas reales: sin papelera, anidadas, secundarias, overflow de IOT,
        # contenedores de vistas materializadas ni tablas externas.
        for owner in owners:
            for f in _filas(cursor, f"""
                SELECT t.table_name, t.temporary, t.duration
                FROM all_tables t
                WHERE t.owner = :1 AND t.nested = 'NO' AND t.secondary = 'N'
                  AND (t.iot_type IS NULL OR t.iot_type = 'IOT')
                  {sin_papelera}
                  {excluir_mviews}
                  {excluir_externas}
            """, (owner,)):
                esquema.tablas[(owner, f["table_name"])] = Tabla(
                    owner=owner, nombre=f["table_name"], destino=f["table_name"],
                    duracion=_texto(f["duration"]) if f["temporary"] == "Y" else None,
                )

        if incluir_sinonimos:
            destinos = {t.destino for t in esquema.tablas.values()}
            # Join con sintaxis clasica de Oracle: funciona en cualquier version.
            for f in _filas(cursor, f"""
                SELECT s.synonym_name, s.table_owner, s.table_name, t.temporary, t.duration
                FROM user_synonyms s, all_tables t
                WHERE t.owner = s.table_owner AND t.table_name = s.table_name
                  AND s.db_link IS NULL
                  {sin_papelera}
            """):
                clave = (f["table_owner"], f["table_name"])
                if clave in esquema.tablas or f["synonym_name"] in destinos:
                    continue
                esquema.tablas[clave] = Tabla(
                    owner=f["table_owner"], nombre=f["table_name"], destino=f["synonym_name"],
                    duracion=_texto(f["duration"]) if f["temporary"] == "Y" else None,
                )
                destinos.add(f["synonym_name"])
                esquema.sinonimos.append((f["synonym_name"], f["table_owner"], f["table_name"]))

        for owner in sorted({o for o, _ in esquema.tablas}):
            _leer_owner(cursor, esquema, owner, dic)

        conteos: dict[str, int] = defaultdict(int)
        for owner in owners:
            marcadores = ", ".join(f":{i + 2}" for i in range(len(OBJETOS_NO_COPIADOS)))
            for f in _filas(cursor, f"""
                SELECT object_type, COUNT(*) AS total FROM all_objects
                WHERE owner = :1 AND object_type IN ({marcadores})
                GROUP BY object_type
            """, (owner, *OBJETOS_NO_COPIADOS)):
                conteos[f["object_type"]] += int(f["total"])
        esquema.no_copiados = dict(conteos)
    finally:
        cursor.close()
    return esquema


def _es_not_null_de_sistema(r: Restriccion, tabla: Tabla | None) -> bool:
    """
    Oracle guarda cada NOT NULL tambien como un CHECK con nombre de sistema
    (SYS_C...). Hay uno por columna obligatoria, asi que leer su condicion
    LONG de a una fila seria lentisimo: se reconocen sin leerla (una sola
    columna, nombre de sistema y la columna ya es NOT NULL). Limite conocido:
    un CHECK sin nombre sobre una sola columna NOT NULL tambien se omite.
    """
    if tabla is None or not r.nombre_de_sistema or len(r.columnas) != 1:
        return False
    return any(c.nombre == r.columnas[0] and not c.nullable for c in tabla.columnas)


def _leer_owner(cursor, esquema: Esquema, owner: str, dic: Diccionario) -> None:
    def tabla(nombre):
        return esquema.tablas.get((owner, nombre))

    # ALL_TAB_COLS (9i+) muestra columnas ocultas y, desde 11g, virtuales;
    # sin ella, ALL_TAB_COLUMNS ya trae solo las visibles.
    if dic.tiene("ALL_TAB_COLS", "HIDDEN_COLUMN"):
        vista_columnas, solo_visibles = "all_tab_cols", "AND hidden_column = 'NO'"
    else:
        vista_columnas, solo_visibles = "all_tab_columns", ""
    columna_virtual = (
        "virtual_column" if dic.tiene("ALL_TAB_COLS", "VIRTUAL_COLUMN") and vista_columnas == "all_tab_cols"
        else "'NO' AS virtual_column"
    )
    columna_indice = "index_name" if dic.tiene("ALL_CONSTRAINTS", "INDEX_NAME") else "NULL AS index_name"

    for f in _filas(cursor, """
        SELECT table_name, comments FROM all_tab_comments
        WHERE owner = :1 AND table_type = 'TABLE' AND comments IS NOT NULL
    """, (owner,)):
        if (t := tabla(f["table_name"])):
            t.comentario = _texto(f["comments"])

    # Sin DATA_DEFAULT (LONG): solo DEFAULT_LENGTH dice si hay que leerlo.
    con_default: list[tuple[Tabla, Columna]] = []
    for f in _filas(cursor, f"""
        SELECT table_name, column_name, data_type, data_type_owner, data_length, data_precision,
               data_scale, char_length, char_used, nullable, default_length, {columna_virtual}
        FROM {vista_columnas}
        WHERE owner = :1 {solo_visibles}
        ORDER BY table_name, column_id
    """, (owner,)):
        if (t := tabla(f["table_name"])):
            columna = Columna(
                nombre=f["column_name"], tipo=f["data_type"], tipo_owner=_texto(f["data_type_owner"]),
                longitud=f["data_length"], precision=f["data_precision"], escala=f["data_scale"],
                char_length=f["char_length"], char_used=_texto(f["char_used"]),
                nullable=f["nullable"] == "Y", virtual=f["virtual_column"] == "YES",
            )
            t.columnas.append(columna)
            if f["default_length"]:
                con_default.append((t, columna))

    for t, columna in con_default:
        valor, error = _leer_long(cursor, f"""
            SELECT data_default FROM {vista_columnas}
            WHERE owner = :1 AND table_name = :2 AND column_name = :3
        """, (owner, t.nombre, columna.nombre))
        if error:
            esquema.avisos.append(
                f"{t.destino}.{columna.nombre}: no se pudo leer su DEFAULT ({error}); se creo sin DEFAULT."
            )
        columna.default = valor

    for f in _filas(cursor, """
        SELECT table_name, column_name, comments FROM all_col_comments
        WHERE owner = :1 AND comments IS NOT NULL
    """, (owner,)):
        if (t := tabla(f["table_name"])):
            t.comentarios_columnas[f["column_name"]] = _texto(f["comments"])

    columnas_restriccion: dict[str, list[str]] = defaultdict(list)
    for f in _filas(cursor, """
        SELECT constraint_name, column_name FROM all_cons_columns
        WHERE owner = :1 ORDER BY constraint_name, position
    """, (owner,)):
        columnas_restriccion[f["constraint_name"]].append(f["column_name"])

    # Se leen todas las restricciones del owner (aunque su tabla no se copie):
    # una foranea de la copia puede referenciar su llave primaria.
    # Sin SEARCH_CONDITION (LONG): la condicion de cada CHECK se lee despues.
    for f in _filas(cursor, f"""
        SELECT table_name, constraint_name, constraint_type, r_owner, r_constraint_name,
               delete_rule, generated, status, {columna_indice}
        FROM all_constraints
        WHERE owner = :1 AND constraint_type IN ('P', 'U', 'R', 'C')
    """, (owner,)):
        if tabla(f["table_name"]) is None and f["constraint_type"] not in ("P", "U"):
            continue
        restriccion = Restriccion(
            owner=owner, tabla=f["table_name"], nombre=f["constraint_name"], tipo=f["constraint_type"],
            columnas=columnas_restriccion.get(f["constraint_name"], []),
            ref_owner=_texto(f["r_owner"]), ref_nombre=_texto(f["r_constraint_name"]),
            regla_borrado=_texto(f["delete_rule"]),
            nombre_de_sistema=f["generated"] == "GENERATED NAME",
            habilitada=f["status"] == "ENABLED", indice=_texto(f["index_name"]),
        )
        esquema.restricciones.append(restriccion)
        if restriccion.tipo == "C" and not _es_not_null_de_sistema(restriccion, tabla(f["table_name"])):
            condicion, error = _leer_long(cursor, """
                SELECT search_condition FROM all_constraints
                WHERE owner = :1 AND constraint_name = :2
            """, (owner, restriccion.nombre))
            restriccion.condicion = condicion
            if error:
                esquema.avisos.append(
                    f"{tabla(f['table_name']).destino}: CHECK {restriccion.nombre} omitido, "
                    f"no se pudo leer su condicion ({error})."
                )

    columnas_indice: dict[tuple[str, str], list[tuple[str, bool]]] = defaultdict(list)
    for f in _filas(cursor, """
        SELECT index_owner, index_name, column_name, descend FROM all_ind_columns
        WHERE table_owner = :1 ORDER BY index_owner, index_name, column_position
    """, (owner,)):
        columnas_indice[(f["index_owner"], f["index_name"])].append((f["column_name"], f["descend"] == "DESC"))

    for f in _filas(cursor, """
        SELECT owner, index_name, table_name, uniqueness, index_type FROM all_indexes
        WHERE table_owner = :1
    """, (owner,)):
        if tabla(f["table_name"]) is None:
            continue
        esquema.indices.append(Indice(
            owner=f["owner"], nombre=f["index_name"], tabla_owner=owner, tabla=f["table_name"],
            unico=f["uniqueness"] == "UNIQUE", tipo=f["index_type"],
            columnas=columnas_indice.get((f["owner"], f["index_name"]), []),
        ))


# ──────────────────────────────────────────────────────────────
# Modo describir: sin diccionario, por la descripcion de un SELECT vacio
# ──────────────────────────────────────────────────────────────

_NOMBRE_ORACLE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,29}(\.[A-Za-z][A-Za-z0-9_$#]{0,29})?$")

# Tipos que el driver informa (DbType.name sin "DB_TYPE_") con DDL fijo.
_TIPOS_FIJOS = {
    "DATE": "DATE", "BLOB": "BLOB", "CLOB": "CLOB", "NCLOB": "NCLOB", "BFILE": "BFILE",
    "LONG": "LONG", "LONG_RAW": "LONG RAW", "ROWID": "ROWID",
    "BINARY_FLOAT": "BINARY_FLOAT", "BINARY_DOUBLE": "BINARY_DOUBLE",
    "TIMESTAMP_TZ": "TIMESTAMP WITH TIME ZONE", "TIMESTAMP_LTZ": "TIMESTAMP WITH LOCAL TIME ZONE",
    "INTERVAL_DS": "INTERVAL DAY TO SECOND", "INTERVAL_YM": "INTERVAL YEAR TO MONTH",
}


def columna_desde_descripcion(info) -> Columna:
    """
    Columna a partir de la descripcion que da el driver (FetchInfo). Los
    textos van en semantica CHAR con el largo en caracteres: la copia puede
    estar en UTF-8 y un acento ocupa 2 bytes (en el Oracle 9i de SERMED, 1).
    """
    tipo = getattr(info.type_code, "name", str(info.type_code)).removeprefix("DB_TYPE_")
    largo = info.display_size or info.internal_size
    base = dict(nombre=info.name, nullable=bool(info.null_ok))
    if tipo in ("VARCHAR", "CHAR"):
        return Columna(tipo="VARCHAR2" if tipo == "VARCHAR" else "CHAR", char_length=largo, char_used="C", **base)
    if tipo in ("NVARCHAR", "NCHAR"):
        return Columna(tipo="NVARCHAR2" if tipo == "NVARCHAR" else "NCHAR", char_length=largo, **base)
    if tipo == "NUMBER":
        if info.scale == -127:
            # NUMBER sin precision (precision 0) o FLOAT(p).
            if info.precision:
                return Columna(tipo="FLOAT", precision=info.precision, **base)
            return Columna(tipo="NUMBER", **base)
        if not info.precision:
            return Columna(tipo="NUMBER", escala=info.scale, **base)
        return Columna(tipo="NUMBER", precision=info.precision, escala=info.scale, **base)
    if tipo == "TIMESTAMP":
        escala = info.scale if info.scale is not None and 0 <= info.scale <= 9 else 6
        return Columna(tipo=f"TIMESTAMP({escala})", **base)
    if tipo in ("RAW", "UROWID"):
        return Columna(tipo=tipo, longitud=info.internal_size, **base)
    if tipo in _TIPOS_FIJOS:
        return Columna(tipo=_TIPOS_FIJOS[tipo], **base)
    # Tipo de objeto u otro que no se puede escribir como DDL: queda comentado.
    return Columna(tipo=tipo, tipo_owner="DESCONOCIDO", **base)


def describir_tablas(conn, nombres: list[str], llaves: dict[str, list[str]] | None = None) -> Esquema:
    """
    Estructura de tablas que el usuario puede consultar aunque el diccionario
    no se las muestre (sinonimo publico, vista, permiso sin acceso al
    catalogo). Ejecuta SELECT * FROM <tabla> WHERE 1 = 0: Oracle describe las
    columnas sin devolver ninguna fila. SOLO LECTURA.

    No trae DEFAULT, comentarios, checks ni indices. La llave primaria se toma
    de ``llaves`` (las que usa el sync), si todas sus columnas existen. Una
    tabla sin acceso queda como aviso, sin detener el resto.
    """
    llaves = {k.upper(): [c.upper() for c in v] for k, v in (llaves or {}).items()}
    esquema = Esquema(owners=[])
    cursor = conn.cursor()
    try:
        for nombre in nombres:
            nombre = nombre.strip().upper()
            if not _NOMBRE_ORACLE.match(nombre):
                esquema.avisos.append(f"{nombre}: nombre invalido, no se consulto.")
                continue
            try:
                # El nombre ya se valido: no se puede enlazar como parametro.
                cursor.execute(f"SELECT * FROM {nombre} WHERE 1 = 0")
                descripcion = list(cursor.description or [])
            except Exception as exc:
                esquema.avisos.append(f"{nombre}: sin acceso ({str(exc).splitlines()[0]}).")
                continue
            destino = nombre.split(".")[-1]
            tabla = Tabla(owner="", nombre=destino, destino=destino,
                          columnas=[columna_desde_descripcion(info) for info in descripcion])
            esquema.tablas[("", destino)] = tabla
            llave = llaves.get(destino)
            existentes = {c.nombre for c in tabla.columnas}
            if llave and set(llave) <= existentes:
                esquema.restricciones.append(Restriccion(
                    owner="", tabla=destino, nombre=f"PK_{destino}"[:30], tipo="P", columnas=llave,
                ))
            elif llave:
                esquema.avisos.append(f"{destino}: sin PK, faltan columnas de la llave {llave}.")
    finally:
        cursor.close()
    return esquema


def copiables(esquema: Esquema) -> list[Restriccion]:
    """Restricciones de tablas que si van en la copia (las P/U de tablas no
    copiadas solo se leen para resolver foraneas)."""
    return [r for r in esquema.restricciones if (r.owner, r.tabla) in esquema.tablas]
