"""
5.1 paso 7b: llena id_paciente en las tablas clinicas de consulta_medica a partir
de no_exp + pk_num (ver services/patient_link_service.py).

Correr DESPUES de corregir_llave_familiares_legacy (si no, vincularia los
familiares migrados con la llave equivocada) y otra vez despues de cualquier
importacion masiva (bulk_create no llena id_paciente).

Idempotente: solo toca filas sin paciente. --dry-run no escribe nada.
"""
from django.core.management.base import BaseCommand

from apps.consulta_medica.services.legacy_migration_control_service import track_run
from apps.consulta_medica.services.patient_link_service import link_existing, unlinked_counts


class Command(BaseCommand):
    help = "Llena id_paciente en las tablas clinicas. Idempotente. --dry-run no escribe nada."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
        parser.add_argument(
            "--sin-crear", action="store_true",
            help="No crear pacientes que falten: sus registros quedan sin vincular.",
        )
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("vincular_id_paciente", options=options, operator=options["operador"]) as run:
            reporte = link_existing(
                dry_run=options["dry_run"],
                create_missing=not options["sin_crear"],
                progress=lambda tabla, i, total: self.stdout.write(f"  {tabla}: {i}/{total} llaves"),
            )
            prefix = "[dry-run] " if options["dry_run"] else ""
            filas = sum(s["rows"] for s in reporte.values())
            creados = sum(s["patients_created"] for s in reporte.values())
            sin_resolver = sum(s["unresolved"] for s in reporte.values())
            for tabla, stats in sorted(reporte.items()):
                if any(stats.values()):
                    self.stdout.write(
                        f"  {tabla}: filas vinculadas {stats['rows']}, pacientes creados "
                        f"{stats['patients_created']}, llaves sin resolver {stats['unresolved']}"
                    )

            pendientes = {t: n for t, n in unlinked_counts().items() if n}
            resumen = (
                f"{prefix}Filas vinculadas: {filas}, pacientes creados: {creados}, "
                f"llaves sin resolver: {sin_resolver}, filas que siguen sin paciente: "
                f"{sum(pendientes.values())}"
            )
            run.rows_read = filas
            run.summary = resumen
            self.stdout.write(self.style.SUCCESS(resumen))
            if pendientes and not options["dry_run"]:
                for tabla, n in sorted(pendientes.items()):
                    self.stdout.write(self.style.WARNING(f"  sin paciente en {tabla}: {n}"))
            elif not options["dry_run"]:
                self.stdout.write("Todas las filas tienen paciente: se puede pasar a la etapa 7e (NOT NULL).")
            self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
