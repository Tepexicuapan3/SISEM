"""
Migra el historial de notas clinicas del legado (MySQL, tabla
`his_notas`) a `consulta_medica.LegacyConsultationRecord` -- archivo de
SOLO LECTURA, NO participa del flujo operativo vivo (no crea
`recepcion.Visit`/`VisitConsultation`). Ver docstring del modelo para el
porque de esa decision.

Mapeo de columnas confirmado contra el DDL real de `his_notas` (dump
`Dump20260903.sql`, 2026-09-14; 604,178 filas en la base viva, rango
2025-01-01 a 2026-09-03 -- el historico 2015-2024 vive en las bases
anuales archivadas del legado, `dbclinicas2015`...`dbclinicas2024_a`, NO
incluidas en este dump).

`det_hisnotcie` (diagnosticos CIE, 8+ millones de filas) NO se migra en
este comando -- es un paso aparte, deliberadamente fuera de alcance aqui.
IMPORTANTE (confirmado post-migracion, 2026-09-14): `no_cie` esta vacio/0
en el 100% de las 604,178 filas de `his_notas` -- el legado NUNCA lo uso
para el diagnostico principal en la practica, a pesar de existir en el
DDL. El diagnostico real vive como TEXTO LIBRE en `ds_diagnostico`
(-> `diagnostic_impression`, 99.3% de cobertura) y el codigo CIE-10
estructurado depende POR COMPLETO de `det_hisnotcie` -- sin esa tabla,
estos registros no tienen diagnostico codificado, solo texto.

Volumen (604k filas): usa `bulk_create(..., update_conflicts=True)` en
lotes -- un `update_or_create` fila por fila con 604k round-trips ORM
seria prohibitivamente lento.
"""

from __future__ import annotations

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin
from apps.consulta_medica.models import LegacyConsultationRecord
from django.core.management.base import BaseCommand

_BATCH_SIZE = 5000

_UPDATE_FIELDS = [
    "no_exp", "pk_num", "consultation_date", "consultation_time",
    "doctor_code_legacy", "clinic_code_legacy", "subjective", "objective",
    "assessment", "plan", "diagnostic_impression", "primary_cie_code_legacy",
    "addendum_legacy", "weight_legacy", "height_legacy", "blood_pressure_legacy",
    "pulse_legacy", "temperature_legacy", "respiration_legacy", "bmi_legacy",
    "glucose_legacy", "is_first_visit_legacy", "status_legacy",
]

_QUERY = """
    SELECT
        cd_snota, no_exp, tp_paciente, fe_nota, hh_nota,
        cd_medico, cd_clinica,
        ds_sintomas, ds_objetivo, ds_analisis, ds_plan, ds_diagnostico,
        no_cie, sw_complemento,
        no_peso, no_estatura, no_ta, no_pulso, no_temp, no_resp, no_imc, no_gluc,
        sw_morbi, sw_status
    FROM his_notas
"""


def _blank_to_none(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _first_visit_flag(sw_morbi):
    sw_morbi = _blank_to_none(sw_morbi)
    if sw_morbi == "1":
        return True
    if sw_morbi == "2":
        return False
    return None


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Migra his_notas (MySQL legado) a "
        "consulta_medica.LegacyConsultationRecord (archivo de solo lectura, "
        "no crea Visit/VisitConsultation). --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        self.add_legacy_mysql_arguments(parser)
        parser.add_argument("--dry-run", action="store_true",
                            help="No escribe nada, solo reporta que haria.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Limitar cantidad de filas del legado (para pruebas).")

    def handle(self, *args, **options):
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

        self.stdout.write(f"Filas leidas de his_notas: {len(rows)}")

        if options["dry_run"]:
            existentes = set(
                LegacyConsultationRecord.objects.values_list("legacy_folio", flat=True)
            )
            creados = sum(1 for row in rows if row["cd_snota"] not in existentes)
            self.stdout.write(self.style.SUCCESS(
                f"[dry-run] Creados: {creados}, Actualizados: {len(rows) - creados}, "
                f"Errores: 0"
            ))
            return

        errores: list[str] = []
        registros: list[LegacyConsultationRecord] = []

        for row in rows:
            no_exp = str(row.get("no_exp") or "").strip()
            legacy_folio = (row.get("cd_snota") or "").strip()
            fecha = row.get("fe_nota")

            if not no_exp or not legacy_folio or not fecha:
                errores.append(
                    f"folio={legacy_folio!r}: falta no_exp/folio/fecha, omitida."
                )
                continue

            try:
                pk_num = int(row.get("tp_paciente") or 0)
            except (TypeError, ValueError):
                errores.append(
                    f"folio={legacy_folio}: tp_paciente invalido "
                    f"({row.get('tp_paciente')!r}), omitida."
                )
                continue

            registros.append(LegacyConsultationRecord(
                legacy_folio=legacy_folio,
                no_exp=no_exp,
                pk_num=pk_num,
                consultation_date=fecha,
                consultation_time=_blank_to_none(row.get("hh_nota")),
                doctor_code_legacy=_blank_to_none(row.get("cd_medico")),
                clinic_code_legacy=row.get("cd_clinica"),
                subjective=_blank_to_none(row.get("ds_sintomas")),
                objective=_blank_to_none(row.get("ds_objetivo")),
                assessment=_blank_to_none(row.get("ds_analisis")),
                plan=_blank_to_none(row.get("ds_plan")),
                diagnostic_impression=_blank_to_none(row.get("ds_diagnostico")),
                primary_cie_code_legacy=row.get("no_cie") or None,
                addendum_legacy=_blank_to_none(row.get("sw_complemento")),
                weight_legacy=_blank_to_none(row.get("no_peso")),
                height_legacy=_blank_to_none(row.get("no_estatura")),
                blood_pressure_legacy=_blank_to_none(row.get("no_ta")),
                pulse_legacy=_blank_to_none(row.get("no_pulso")),
                temperature_legacy=_blank_to_none(row.get("no_temp")),
                respiration_legacy=_blank_to_none(row.get("no_resp")),
                bmi_legacy=_blank_to_none(row.get("no_imc")),
                glucose_legacy=_blank_to_none(row.get("no_gluc")),
                is_first_visit_legacy=_first_visit_flag(row.get("sw_morbi")),
                status_legacy=_blank_to_none(row.get("sw_status")),
            ))

        total_antes = LegacyConsultationRecord.objects.count()

        for inicio in range(0, len(registros), _BATCH_SIZE):
            lote = registros[inicio:inicio + _BATCH_SIZE]
            LegacyConsultationRecord.objects.bulk_create(
                lote,
                update_conflicts=True,
                unique_fields=["legacy_folio"],
                update_fields=_UPDATE_FIELDS,
            )
            self.stdout.write(
                f"  ... {min(inicio + _BATCH_SIZE, len(registros))}/{len(registros)}"
            )

        total_despues = LegacyConsultationRecord.objects.count()
        creados = total_despues - total_antes
        actualizados = len(registros) - creados

        prefix = ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Creados: {creados}, Actualizados: {actualizados}, "
            f"Errores: {len(errores)}"
        ))
        for err in errores[:50]:
            self.stdout.write(self.style.WARNING(f"  - {err}"))
        if len(errores) > 50:
            self.stdout.write(self.style.WARNING(f"  ... y {len(errores) - 50} mas"))
