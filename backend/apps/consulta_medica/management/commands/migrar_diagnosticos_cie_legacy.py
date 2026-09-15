"""
Migra los diagnosticos CIE-10 del legado (MySQL, tabla `det_hisnotcie`) a
`consulta_medica.LegacyConsultationDiagnosis` -- archivo de SOLO LECTURA,
mismo espiritu que `migrar_notas_clinicas_legacy.py`.

Confirmado contra el DDL/datos reales del dump `Dump20260903.sql`
(2026-09-14): 529,315 filas reales en la base viva -- el
`AUTO_INCREMENT=8036505` de la tabla es un contador historico acumulado
(archivado/borrado de por medio), NO la cantidad de filas que existen hoy.
430,865 notas distintas tienen al menos un diagnostico.

`record` (FK a LegacyConsultationRecord) se resuelve por `legacy_folio`
(= `cd_snota`) -- se precarga un dict completo en memoria (604k pares
folio->id, liviano) para evitar 529k queries individuales. Si un
diagnostico no tiene nota correspondiente en el dump (relacion logica del
legado, sin FK fisico garantizado), `record` queda en None pero la fila
se migra igual con `legacy_folio` crudo -- no se descarta.
"""

from __future__ import annotations

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin
from apps.consulta_medica.models import LegacyConsultationDiagnosis, LegacyConsultationRecord
from django.core.management.base import BaseCommand

_BATCH_SIZE = 5000

_UPDATE_FIELDS = [
    "record", "legacy_folio", "cie_code_legacy",
    "doctor_code_legacy", "clinic_code_legacy", "status_legacy",
]

_QUERY = """
    SELECT cd_detcie, cd_snota, cd_cie, cd_medico, cd_clinica, sw_status
    FROM det_hisnotcie
"""


def _blank_to_none(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Migra det_hisnotcie (MySQL legado) a "
        "consulta_medica.LegacyConsultationDiagnosis (archivo de solo lectura). "
        "--dry-run no escribe nada."
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

        self.stdout.write(f"Filas leidas de det_hisnotcie: {len(rows)}")

        self.stdout.write("Precargando mapa folio->record de LegacyConsultationRecord...")
        folio_a_record_id = dict(
            LegacyConsultationRecord.objects.values_list("legacy_folio", "id_legacy_record")
        )
        self.stdout.write(f"  {len(folio_a_record_id)} folios en memoria.")

        if options["dry_run"]:
            existentes = set(
                LegacyConsultationDiagnosis.objects.values_list("legacy_id", flat=True)
            )
            sin_record = sum(
                1 for row in rows if row["cd_snota"] not in folio_a_record_id
            )
            creados = sum(1 for row in rows if row["cd_detcie"] not in existentes)
            self.stdout.write(self.style.SUCCESS(
                f"[dry-run] Creados: {creados}, Actualizados: {len(rows) - creados}, "
                f"Sin record asociado (huerfanos, se migran igual): {sin_record}, Errores: 0"
            ))
            return

        errores: list[str] = []
        diagnosticos: list[LegacyConsultationDiagnosis] = []
        huerfanos = 0

        for row in rows:
            legacy_id = row.get("cd_detcie")
            legacy_folio = (row.get("cd_snota") or "").strip()
            cie_code = row.get("cd_cie")

            if not legacy_id or not legacy_folio or not cie_code:
                errores.append(
                    f"cd_detcie={legacy_id!r}: falta id/folio/cie, omitida."
                )
                continue

            record_id = folio_a_record_id.get(legacy_folio)
            if record_id is None:
                huerfanos += 1

            diagnosticos.append(LegacyConsultationDiagnosis(
                legacy_id=legacy_id,
                record_id=record_id,
                legacy_folio=legacy_folio,
                cie_code_legacy=cie_code,
                doctor_code_legacy=_blank_to_none(row.get("cd_medico")),
                clinic_code_legacy=row.get("cd_clinica"),
                status_legacy=_blank_to_none(row.get("sw_status")),
            ))

        total_antes = LegacyConsultationDiagnosis.objects.count()

        for inicio in range(0, len(diagnosticos), _BATCH_SIZE):
            lote = diagnosticos[inicio:inicio + _BATCH_SIZE]
            LegacyConsultationDiagnosis.objects.bulk_create(
                lote,
                update_conflicts=True,
                unique_fields=["legacy_id"],
                update_fields=_UPDATE_FIELDS,
            )
            self.stdout.write(
                f"  ... {min(inicio + _BATCH_SIZE, len(diagnosticos))}/{len(diagnosticos)}"
            )

        total_despues = LegacyConsultationDiagnosis.objects.count()
        creados = total_despues - total_antes
        actualizados = len(diagnosticos) - creados

        self.stdout.write(self.style.SUCCESS(
            f"Creados: {creados}, Actualizados: {actualizados}, "
            f"Sin record asociado (huerfanos, migrados igual): {huerfanos}, "
            f"Errores: {len(errores)}"
        ))
        for err in errores[:50]:
            self.stdout.write(self.style.WARNING(f"  - {err}"))
        if len(errores) > 50:
            self.stdout.write(self.style.WARNING(f"  ... y {len(errores) - 50} mas"))
