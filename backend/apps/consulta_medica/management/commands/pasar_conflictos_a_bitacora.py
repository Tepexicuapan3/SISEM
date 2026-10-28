"""
5.1 paso 11: pasa a cns_bitacora_cambios (motivo "CONFLICTO MIGRACION") los
conflictos de migracion que ya estaban en cns_conflicto_migracion. Los nuevos
ya entran solos. cns_conflicto_migracion se conserva para la revision humana.

Los conflictos de familiares con la llave del legado (cd_familiar) se resuelven
por cns_identificador_paciente. Idempotente. --dry-run no escribe nada.
"""
from django.core.management.base import BaseCommand

from apps.consulta_medica.services.legacy_migration_control_service import (
    backfill_conflicts_to_change_log,
    track_run,
)


class Command(BaseCommand):
    help = "Pasa los conflictos de migracion existentes a la bitacora de cambios. Idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("pasar_conflictos_a_bitacora", options=options, operator=options["operador"]) as run:
            counts = backfill_conflicts_to_change_log(dry_run=options["dry_run"])
            prefix = "[dry-run] " if options["dry_run"] else ""
            resumen = (
                f"{prefix}Pasados a la bitacora: {counts['pasados']}, ya estaban: {counts['ya_estaban']}, "
                f"sin paciente: {counts['sin_paciente']}"
            )
            run.rows_read = sum(counts.values())
            run.summary = resumen
            self.stdout.write(self.style.SUCCESS(resumen))
            if counts["sin_paciente"]:
                self.stdout.write(self.style.WARNING(
                    "  Los conflictos sin paciente suelen ser familiares con la llave del legado: "
                    "revisar que su cd_familiar este registrado (registrar_llaves_legado)."
                ))
            self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
