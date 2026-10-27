"""
Puente hacia el legado: registra el CD_FAMILIAR de los familiares de SERMED
que ya existen en SIRES y todavia no lo tienen (ver services/legado_llaves.py).
Se corre despues de la recarga nocturna de la copia (runbook legado-tres-capas,
1.7); al abrir un familiar nuevo ya se intenta en el momento.

Idempotente. Lee la copia del legado (solo lectura) y escribe solo
identificadores en SIRES, cada uno con su fila en cns_bitacora_cambios (motivo
LLAVE LEGADO). Los casos dudosos se listan para revisarlos: nunca se adivina.
--dry-run no escribe nada.
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from apps.consulta_medica.models import Patient, PatientIdentifier
from apps.consulta_medica.services import legado_archivo, legado_llaves
from apps.consulta_medica.services.change_log_service import PROCESS_MIGRATION
from apps.consulta_medica.services.legacy_migration_control_service import track_run


class Command(BaseCommand):
    help = (
        "Registra el CD_FAMILIAR del legado de los familiares de SIRES que no lo tienen. "
        "Idempotente. --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        if not legado_archivo.disponible():
            raise CommandError("La copia del legado no esta configurada (LEGADO_NAME).")
        with track_run("registrar_llaves_legado", options=options, operator=options["operador"]) as run:
            mapa = legado_llaves.cargar_mapa()
            con_puente = set(
                PatientIdentifier.objects.filter(
                    id_type=PatientIdentifier.IdType.CD_FAMILIAR, status=PatientIdentifier.Status.ACTIVE,
                ).values_list("patient_id", flat=True)
            )
            familiares = Patient.objects.filter(pk_num__gt=0).exclude(pk__in=con_puente).order_by("id_patient")
            resultados = Counter()
            dudosos = []
            for paciente in familiares.iterator(chunk_size=2000):
                if options["dry_run"]:
                    resultado = mapa.resolver(paciente.no_exp, paciente.pk_num)[1]
                else:
                    resultado = legado_llaves.registrar_cd_familiar(paciente, mapa, user=PROCESS_MIGRATION)
                resultados[resultado] += 1
                if resultado in (legado_llaves.AMBIGUO, legado_llaves.CONFLICTO):
                    dudosos.append(f"id_paciente={paciente.pk} {paciente.no_exp}/{paciente.pk_num}: {resultado}")

            run.rows_read = sum(resultados.values())
            prefix = "[dry-run] " if options["dry_run"] else ""
            resumen = (
                f"{prefix}Familiares sin puente: {run.rows_read}, "
                f"Registrados: {resultados[legado_llaves.REGISTRADO]}, "
                f"No estan en el legado: {resultados[legado_llaves.SIN_LEGADO]}, "
                f"Dudosos: {len(dudosos)}"
            )
            run.summary = resumen
            self.stdout.write(self.style.SUCCESS(resumen))
            for dudoso in dudosos:
                self.stdout.write(self.style.WARNING(f"  {dudoso}"))
            self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
