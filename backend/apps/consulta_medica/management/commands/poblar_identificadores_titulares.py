"""
Llenado inicial de cns_identificador_paciente para los TITULARES que ya existen
en cns_paciente (documento "Historia Clinica Unificada", 5.1 y seccion 8).

Solo titulares (pk_num 0 -> identificador NO_EXP). Los familiares quedan fuera
a proposito: los migrados del legado tienen en pk_num el cd_familiar de
dbclinicas (bug documentado), y registrarlo como PK_NUM guardaria el error en
la tabla oficial. Sus identificadores se registran al corregir ese mapeo.

Idempotente. Cada alta queda en cns_bitacora_cambios (motivo MIGRACION) y la
ejecucion en cns_bitacora_migracion. --dry-run no escribe nada.
"""
from django.core.management.base import BaseCommand

from apps.consulta_medica.models import ChangeLog, Patient, PatientIdentifier
from apps.consulta_medica.services.change_log_service import PROCESS_MIGRATION
from apps.consulta_medica.services.legacy_migration_control_service import track_run
from apps.consulta_medica.services.patient_identifier_service import (
    IdentifierConflict,
    register_identifier,
)


class Command(BaseCommand):
    help = (
        "Registra el identificador NO_EXP de cada titular de cns_paciente. "
        "Idempotente. --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("poblar_identificadores_titulares", options=options, operator=options["operador"]) as run:
            titulares = Patient.objects.filter(pk_num=0).order_by("id_patient")
            ya_tienen = set(
                PatientIdentifier.objects.filter(
                    id_type=PatientIdentifier.IdType.NO_EXP, status=PatientIdentifier.Status.ACTIVE,
                ).values_list("patient_id", flat=True)
            )
            creados = existentes = 0
            conflictos = []

            for paciente in titulares.iterator(chunk_size=2000):
                if paciente.pk in ya_tienen:
                    existentes += 1
                    continue
                if options["dry_run"]:
                    creados += 1
                    continue
                try:
                    register_identifier(
                        paciente, PatientIdentifier.IdType.NO_EXP, paciente.no_exp,
                        reason=ChangeLog.Reason.MIGRATION, user=PROCESS_MIGRATION,
                    )
                    creados += 1
                except IdentifierConflict as exc:
                    conflictos.append(str(exc))

            run.rows_read = creados + existentes + len(conflictos)
            prefix = "[dry-run] " if options["dry_run"] else ""
            resumen = (
                f"{prefix}Titulares: {run.rows_read}, Registrados: {creados}, "
                f"Ya tenian NO_EXP: {existentes}, Conflictos: {len(conflictos)}"
            )
            run.summary = resumen
            self.stdout.write(self.style.SUCCESS(resumen))
            for conflicto in conflictos:
                self.stdout.write(self.style.WARNING(f"  {conflicto}"))
            self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
