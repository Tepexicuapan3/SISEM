"""
check_medico_identity — chequeo READ-ONLY de integridad de identidad médico/usuario.

Parte de la red de seguridad (Fase 1) del cambio `medico-pk-independiente`
(ver Engram, topic_key sdd/medico-pk-independiente/design, sección 1).

No modifica NADA. No hay constraint declarativo en PostgreSQL que exprese
"este id de usuario también es un médico" (los CHECK no cruzan tablas), así
que este comando es el instrumento correcto: una aserción, no un schema.

Se diseñó para correr ANTES del switch de PK (Fase 4): valida la relación
`<tabla>.medico_id -> cat_medicos.id_usuario`, que es la semántica vigente
mientras `id_usuario` siga siendo la PK de `cat_medicos`. Se reusa también
dentro de la migración de backfill (0006_backfill_legacy_ids, tarea F3-02)
llamando directamente a `run_checks()` — NO se invoca el comando de gestión
desde dentro de una migración (evita el problema de mezclar modelos
históricos de la migración con los modelos "vivos" que importa este
archivo).

Salida: `run_checks()` devuelve `(aborts: list[str], warnings: list[str])`.
Si `aborts` no está vacío, el llamador (comando o migración) debe abortar.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection

# Las 9 columnas FK (8 modelos) que hoy apuntan al valor de
# cat_medicos.id_usuario (ver propuesta, obs #467, sección 2 — inventario
# verificado leyendo el código, no asumido).
_MEDICO_FK_COLUMNS = [
    ("rel_medico_especialidad", "medico_id"),
    ("rel_medico_centro", "medico_id"),
    ("rel_medico_consultorio", "medico_id"),
    ("rel_medico_excepcion", "medico_id"),
    ("rel_medico_cobertura", "medico_suplente_id"),
    ("rel_medico_cobertura", "medico_titular_id"),
    ("citas_medicas", "medico_id"),
    ("citas_horarios_disponibles", "medico_id"),
    ("almacen_consumos_consulta", "medico_id"),
]


def _table_exists(table_name: str) -> bool:
    return table_name in connection.introspection.table_names()


def _fetchall(sql: str, params=None) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.fetchall()


def run_checks() -> tuple[list[str], list[str]]:
    """
    Corre A1-A7. Devuelve (aborts, warnings) — ambas listas de strings
    legibles. `aborts` vacía == check limpio (no implica "warnings" vacía,
    A3/A4 son WARN por diseño, no ABORT).
    """
    aborts: list[str] = []
    warnings: list[str] = []

    if not _table_exists("cat_medicos"):
        # DB recién creada / sin datos todavía (p.ej. test runner). Nada que chequear.
        return aborts, warnings

    # A6 — cat_medicos.id_usuario duplicado o NULL (hoy imposible por ser PK,
    # se asegura igual para detectar drift post-switch si algo se corrió mal).
    dup_or_null = _fetchall(
        "SELECT id_usuario, COUNT(*) FROM cat_medicos "
        "GROUP BY id_usuario HAVING COUNT(*) > 1 OR id_usuario IS NULL"
    )
    if dup_or_null:
        aborts.append(
            "A6: cat_medicos.id_usuario duplicado o NULL para "
            f"{len(dup_or_null)} valor(es): {dup_or_null[:20]}"
        )

    # A1 + A2 — por cada una de las 9 columnas FK: filas sin match en
    # cat_medicos.id_usuario (A1, ABORT) y conteo baseline por tabla (A2,
    # se imprime/devuelve para que el llamador lo persista como línea base).
    baseline_counts: dict[str, int] = {}
    for table, column in _MEDICO_FK_COLUMNS:
        if not _table_exists(table):
            continue
        total = _fetchall(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NOT NULL')[0][0]
        baseline_counts[f"{table}.{column}"] = total

        orphans = _fetchall(
            f'SELECT t."{column}" FROM "{table}" t '
            f'WHERE t."{column}" IS NOT NULL '
            f'AND NOT EXISTS (SELECT 1 FROM cat_medicos m WHERE m.id_usuario = t."{column}")'
        )
        if orphans:
            valores = sorted({row[0] for row in orphans})[:50]
            aborts.append(
                f"A1: {table}.{column} tiene {len(orphans)} fila(s) sin match en "
                f"cat_medicos.id_usuario. Valores (máx 50): {valores}"
            )

    # A7 — citas_horarios_disponibles con medico_id que no existe en el catálogo
    # (subconjunto de A1 para esa tabla puntual, redundante a propósito — el
    # design lo pide como chequeo explícito separado porque es la tabla de
    # mayor volumen potencial).
    if _table_exists("citas_horarios_disponibles"):
        huerfanas = _fetchall(
            'SELECT COUNT(*) FROM citas_horarios_disponibles t '
            'WHERE t.medico_id IS NOT NULL '
            'AND NOT EXISTS (SELECT 1 FROM cat_medicos m WHERE m.id_usuario = t.medico_id)'
        )[0][0]
        if huerfanas:
            aborts.append(
                f"A7: citas_horarios_disponibles tiene {huerfanas} fila(s) huérfana(s) "
                "(medico_id sin match en cat_medicos.id_usuario)."
            )

    # A3 — visits.doctor_id sin match en cat_medicos.id_usuario: usuarios que
    # atendieron pero NO están en el catálogo de médicos. WARN, no ABORT —
    # son las "minas" de R1 (conflación doctor_id/medico_id), no un error de
    # integridad en sí.
    if _table_exists("rcp_visits"):
        a3 = _fetchall(
            "SELECT COUNT(*) FROM rcp_visits v WHERE v.doctor_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM cat_medicos m WHERE m.id_usuario = v.doctor_id)"
        )[0][0]
        if a3:
            warnings.append(
                f"A3: rcp_visits tiene {a3} fila(s) con doctor_id que NO está en "
                "cat_medicos (usuario atendió sin estar en el catálogo de médicos)."
            )

    # A4 — mismo criterio para consulta_medica.VisitConsultation.
    if _table_exists("cns_visit_consultation"):
        a4 = _fetchall(
            "SELECT COUNT(*) FROM cns_visit_consultation c WHERE c.id_doctor IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM cat_medicos m WHERE m.id_usuario = c.id_doctor)"
        )[0][0]
        if a4:
            warnings.append(
                f"A4: cns_visit_consultation tiene {a4} fila(s) con id_doctor que NO "
                "está en cat_medicos."
            )

    # A5 — divergencias YA EXISTENTES hoy entre rcp_visits.doctor_id y
    # citas_medicas.medico_id para la misma cita (join por folio/appointment_id).
    if _table_exists("rcp_visits") and _table_exists("citas_medicas"):
        # Evita `IS DISTINCT FROM` (Postgres siempre lo soporta, pero SQLite
        # solo desde 3.39 -- este comando puede correr contra el motor de
        # tests del proyecto, que es SQLite, ver 0004_expand_surrogate_pk.py).
        a5 = _fetchall(
            "SELECT COUNT(*) FROM citas_medicas c "
            "JOIN rcp_visits v ON v.appointment_id = c.folio "
            "WHERE (v.doctor_id IS NULL AND c.medico_id IS NOT NULL) "
            "OR (v.doctor_id IS NOT NULL AND c.medico_id IS NULL) "
            "OR (v.doctor_id <> c.medico_id)"
        )[0][0]
        if a5:
            aborts.append(
                f"A5: {a5} cita(s) con divergencia entre rcp_visits.doctor_id y "
                "citas_medicas.medico_id para el mismo folio -- ya existe conflación "
                "hoy, antes de tocar el esquema."
            )

    return aborts, warnings


class Command(BaseCommand):
    help = (
        "Chequeo read-only de integridad de identidad médico/usuario (A1-A7). "
        "Exit code != 0 si hay algún ABORT. Parte de la red de seguridad del "
        "cambio medico-pk-independiente (Fase 1) -- ver Engram "
        "sdd/medico-pk-independiente/design."
    )

    def handle(self, *args, **options):
        aborts, warnings = run_checks()

        for w in warnings:
            self.stdout.write(self.style.WARNING(f"WARN {w}"))

        if aborts:
            for a in aborts:
                self.stderr.write(self.style.ERROR(f"ABORT {a}"))
            self.stderr.write(
                self.style.ERROR(f"\ncheck_medico_identity: {len(aborts)} hallazgo(s) ABORT.")
            )
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"check_medico_identity: OK (0 ABORT, {len(warnings)} WARN)."
            )
        )
