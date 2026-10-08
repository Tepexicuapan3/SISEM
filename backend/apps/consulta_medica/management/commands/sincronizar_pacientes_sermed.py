"""
5.1 paso 6: sincroniza los pacientes de SIRES con la replica de SERMED
(services/sermed_sync_service.py). Solo lee la replica; nunca escribe en Oracle.

Sin --no-exp recorre todos los pacientes (carga completa). Cada cambio queda en
cns_bitacora_cambios (motivo "SINCRONIZACION SERMED") y la ejecucion en
cns_bitacora_migracion. --reporte deja en un .csv las discrepancias para
Capital Humano. --dry-run no escribe nada.
"""
import csv

from django.core.management.base import BaseCommand

from apps.consulta_medica.models import Patient
from apps.consulta_medica.services.legacy_migration_control_service import track_run
from apps.consulta_medica.services.sermed_sync_service import sync_patients


class Command(BaseCommand):
    help = "Sincroniza nombre, fecha de nacimiento, sexo y CURP de titulares desde la replica de SERMED."

    def add_arguments(self, parser):
        parser.add_argument("--no-exp", default=None, help="Solo los pacientes de este expediente.")
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
        parser.add_argument("--reporte", default=None, help="Ruta de un .csv con las discrepancias.")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("sincronizar_pacientes_sermed", options=options, operator=options["operador"]) as run:
            patients = Patient.objects.order_by("id_patient")
            if options["no_exp"]:
                patients = patients.filter(no_exp=options["no_exp"].strip())

            result = sync_patients(patients.iterator(chunk_size=500), dry_run=options["dry_run"])

            prefix = "[dry-run] " if options["dry_run"] else ""
            resumen = prefix + ", ".join(f"{k}={v}" for k, v in sorted(result.counts.items())) or f"{prefix}sin pacientes"
            run.rows_read = result.counts.get("procesados", 0)
            run.summary = resumen
            self.stdout.write(self.style.SUCCESS(resumen))

            for d in result.discrepancies[:30]:
                self.stdout.write(self.style.WARNING(f"  {d.kind}: no_exp={d.no_exp} pk_num={d.pk_num} {d.detail}"))
            if len(result.discrepancies) > 30:
                self.stdout.write(f"  ... y {len(result.discrepancies) - 30} mas (usar --reporte).")

            if options["reporte"]:
                with open(options["reporte"], "w", newline="", encoding="utf-8") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(["tipo", "id_paciente", "no_exp", "pk_num", "detalle"])
                    for d in result.discrepancies:
                        writer.writerow([d.kind, d.patient_id, d.no_exp, d.pk_num if d.pk_num is not None else "", d.detail])
                self.stdout.write(f"Reporte de discrepancias: {options['reporte']}")
            self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
