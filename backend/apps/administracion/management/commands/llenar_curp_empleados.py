from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.administracion.services.curp_empleados_service import BATCH_SIZE, llenar_curp_empleados
from apps.administracion.services.sync_service import obtener_conexion_oracle
from apps.consulta_medica.services.legacy_migration_control_service import track_run


class Command(BaseCommand):
    help = (
        "Llenado inicial de curp y cd_sexo en la replica cat_empleados desde Oracle "
        "(solo SELECT a Oracle). Copia los valores tal cual. Idempotente. "
        "Requiere storage/expedientes-ddl/003_curp_sexo_cat_empleados.sql aplicado. "
        "--dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="No escribe nada, solo reporta que haria.")
        parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                            help=f"Filas por lote (por defecto {BATCH_SIZE}).")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("llenar_curp_empleados", options=options, operator=options["operador"]) as run:
            try:
                oracle_conn = obtener_conexion_oracle()
            except Exception as exc:
                raise CommandError(f"No se pudo conectar a Oracle: {exc}") from exc

            try:
                conteos = llenar_curp_empleados(
                    oracle_conn,
                    dry_run=options["dry_run"],
                    batch_size=options["batch_size"],
                )
            finally:
                oracle_conn.close()

            prefix = "[dry-run] " if options["dry_run"] else ""
            resumen = (
                f"{prefix}Leidos de Oracle: {conteos['leidos']}, "
                f"Actualizados: {conteos['actualizados']}, "
                f"Sin cambio: {conteos['sin_cambio']}, "
                f"No estan en la replica: {conteos['no_en_replica']}"
            )
            run.rows_read = conteos["leidos"]
            run.summary = resumen
            self.stdout.write(self.style.SUCCESS(resumen))
            self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
