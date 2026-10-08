"""
Corrige el bug CD_FAMILIAR: los comandos migrar_*_legacy guardaron el tp_paciente
del legado (cat_familiar.cd_familiar) como si fuera el PK_NUM de SERMED.

Lee el cat_familiar del MySQL legado (SOLO SELECT) para saber, por titular, que
numeros son cd_familiar y cuales PK_NUM. Cada llave (no_exp, pk_num) de SIRES se
clasifica y solo se corrige cuando el caso es inequivoco; lo dudoso va al reporte
(ver services/family_key_fix_service.py).

Idempotente. Cada paciente corregido queda en cns_bitacora_cambios (motivo
"CORRECCION CD_FAMILIAR") y la ejecucion en cns_bitacora_migracion. Hacer un
respaldo de la base antes y correr primero con --dry-run.
"""
import csv

from django.core.management.base import BaseCommand

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin
from apps.consulta_medica.services.family_key_fix_service import FIXABLE, run_fix
from apps.consulta_medica.services.legacy_family_map import LegacyFamilyMap
from apps.consulta_medica.services.legacy_migration_control_service import track_run

_MAX_LISTADO = 50


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Corrige la llave de los familiares migrados del legado (cd_familiar guardado "
        "como pk_num). Solo lee del legado. Idempotente. --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        self.add_legacy_mysql_arguments(parser)
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo clasifica.")
        parser.add_argument("--reporte", default=None,
                            help="Ruta de un .csv con todas las llaves que requieren revision humana.")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("corregir_llave_familiares_legacy", options=options, operator=options["operador"]) as run:
            conn = self.conectar_legado(options)
            try:
                fmap = LegacyFamilyMap.from_legacy_connection(conn)
            finally:
                conn.close()
            self.stdout.write(
                f"cat_familiar del legado: {len(fmap.titular_by_cd)} familiares, "
                f"{len(fmap.pk_by_cd)} con PK_NUM traducible, "
                f"{len(fmap.ambiguous_cds)} con PK_NUM repetido."
            )

            resultado = run_fix(
                fmap, dry_run=options["dry_run"],
                progress=lambda i, total: self.stdout.write(f"  ... {i}/{total} llaves"),
            )
            counts, review = resultado["counts"], resultado["review"]

            prefix = "[dry-run] " if options["dry_run"] else ""
            corregibles = sum(n for kind, n in counts.items() if kind in FIXABLE)
            resumen = (
                f"{prefix}Llaves de familiar: {sum(counts.values())}, "
                f"corregidas o ya correctas: {corregibles}, a revision: {len(review)}. "
                + ", ".join(f"{kind}={n}" for kind, n in sorted(counts.items()))
            )
            run.rows_read = sum(counts.values())
            run.summary = resumen
            self.stdout.write(self.style.SUCCESS(resumen))
            for table, count in sorted(resultado["moved"].items()):
                self.stdout.write(f"  filas movidas en {table}: {count}")

            for decision in review[:_MAX_LISTADO]:
                self.stdout.write(self.style.WARNING(
                    f"  {decision.kind}: no_exp={decision.no_exp} valor={decision.value} {decision.detail}"
                ))
            if len(review) > _MAX_LISTADO:
                self.stdout.write(f"  ... y {len(review) - _MAX_LISTADO} mas (usar --reporte).")

            if options["reporte"]:
                with open(options["reporte"], "w", newline="", encoding="utf-8") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(["tipo", "no_exp", "valor_guardado", "pk_num_destino", "detalle"])
                    for decision in review:
                        writer.writerow([decision.kind, decision.no_exp, decision.value,
                                         decision.target_pk or "", decision.detail])
                self.stdout.write(f"Reporte de revision: {options['reporte']}")
            self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
