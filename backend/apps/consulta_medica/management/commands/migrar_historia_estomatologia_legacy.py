"""
Migra la historia clinica de ESTOMATOLOGIA del legado (MySQL, `his_clinicad`,
~24,100 filas segun el AUTO_INCREMENT del dump 2026-09-03) a la historia
clinica unificada. Columnas confirmadas contra el DDL real del dump.

Mapeo (documento "Historia Clinica Unificada", seccion 7):
  cd_ocupacion, cd_edocivil        -> PACIENTE, con la regla de conflictos (seccion 8)
  sw_diabetes/cancer/presalta/baja -> FamilyHistory (sin sufijo = FAMILIAR)
  ds_muerte                        -> FamilyHistory finado
  sw_*p, sw_asma/hepatitis/sida    -> PersonalHistory (con sufijo p = PERSONAL)
  sw_tabaquismo/alcoholismo/toxic. -> Habit; ds_habitos/ds_alimentos -> Habit
  ds_antquir                       -> SurgicalHistory
  ds_antecedentes, ds_terapias     -> HistoricalNote
  ds_ale* (6 columnas)             -> Allergy con su categoria
  no_peso ... no_resp              -> LegacyVitalSigns (sin consulta, fecha desconocida)

Idempotente (legacy_ref "his_clinicad:<no_hisclin>"). No se ejecuta de forma
autonoma contra el servidor real: lo corre el usuario en su ventana de
mantenimiento. Usar --dry-run primero. Cada ejecucion queda en
cns_bitacora_migracion (--operador) y cada discrepancia de la ficha en
cns_conflicto_migracion.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin
from apps.catalogos.models import EdoCivil, Ocupaciones
from apps.consulta_medica.management.commands.migrar_historial_clinico_legacy import _norm
from apps.consulta_medica.services.legacy_history_import_service import LegacyHistoryImporter
from apps.consulta_medica.services.legacy_migration_control_service import track_run

_QUERY = """
    SELECT a.*, b.ds_ocupacion, d.ds_edocivil
    FROM his_clinicad a
    LEFT JOIN cat_ocupacion b ON a.cd_ocupacion = b.cd_ocupacion
    LEFT JOIN cat_edocivil  d ON a.cd_edocivil  = d.cd_edocivil
    ORDER BY a.no_hisclin
"""

_CATALOGOS = (
    ("occupation_id", "ds_ocupacion", Ocupaciones),
    ("marital_status_id", "ds_edocivil", EdoCivil),
)


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Migra his_clinicad (estomatologia, MySQL legado) a la historia clinica "
        "unificada. Idempotente. --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        self.add_legacy_mysql_arguments(parser)
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
        parser.add_argument("--limit", type=int, default=None, help="Limitar filas (pruebas).")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("migrar_historia_estomatologia_legacy", options=options,
                       operator=options["operador"]) as run:
            self._migrar(run, options)

    def _migrar(self, run, options):
        conn = self.conectar_legado(options)
        try:
            with conn.cursor() as cursor:
                query = _QUERY
                if options["limit"]:
                    query += f" LIMIT {int(options['limit'])}"
                cursor.execute(query)
                rows = cursor.fetchall()
        finally:
            conn.close()

        self.stdout.write(f"Filas leidas de his_clinicad: {len(rows)}")
        run.rows_read = len(rows)

        catalogo_por_nombre = {
            fk_field: {_norm(obj.name): obj.id for obj in modelo.objects.all()}
            for fk_field, _col, modelo in _CATALOGOS
        }
        importer = LegacyHistoryImporter(run=run)
        importadas = 0
        ya_importadas = 0
        errores: list[str] = []

        for row in rows:
            no_exp = str(row.get("no_exp") or "").strip()
            if not no_exp:
                errores.append(f"his_clinicad {row.get('no_hisclin')}: sin no_exp, omitida.")
                continue
            try:
                pk_num = int(row.get("tp_paciente") or 0)
            except (TypeError, ValueError):
                errores.append(f"no_exp={no_exp}: tp_paciente invalido ({row.get('tp_paciente')!r}), omitida.")
                continue

            catalog_ids = {
                fk_field: catalogo_por_nombre[fk_field].get(_norm(row.get(col)))
                for fk_field, col, _modelo in _CATALOGOS
                if row.get(col)
            }

            if options["dry_run"]:
                if importer.already_imported(f"his_clinicad:{row.get('no_hisclin')}"):
                    ya_importadas += 1
                else:
                    importadas += 1
                continue

            try:
                with transaction.atomic():
                    if importer.import_his_clinicad_row(
                        row, no_exp=no_exp, pk_num=pk_num, catalog_ids=catalog_ids,
                    ):
                        importadas += 1
                    else:
                        ya_importadas += 1
            except DatabaseError as exc:
                errores.append(f"no_exp={no_exp}: error de base de datos ({exc}), omitida.")

        prefix = "[dry-run] " if options["dry_run"] else ""
        resumen = f"{prefix}Importadas: {importadas}, Ya importadas: {ya_importadas}, Errores: {len(errores)}"
        detalle = (
            f"{prefix}Registros permanentes: {importer.counters['records']}, "
            f"Notas historicas: {importer.counters['notes']}, "
            f"Alergias: {importer.counters['allergies']}, "
            f"Signos vitales legado: {importer.counters['vitals']}, "
            f"Conflictos de ficha: {importer.counters['conflicts']}"
        )
        run.summary = f"{resumen}. {detalle}"
        self.stdout.write(self.style.SUCCESS(resumen))
        self.stdout.write(detalle)
        self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
        for err in errores:
            self.stdout.write(self.style.WARNING(f"  - {err}"))
