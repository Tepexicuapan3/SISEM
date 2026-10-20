"""
resolve_hsp_doctor_codes -- puente de los codigos legados de medico en
hospitalizacion (cambio `medicos-id-no-medico`, R8).

REGLA DE ORO: un codigo legado nunca es `CatMedico.id`. Todo pasa por
`LegacyMedico` y su puente `medico_actual`:

- `admitting_doctor_code_legacy` (`cd_medicoing`) y
  `discharge_doctor_code_legacy` (`cd_medicoalta`) son AMBOS un `no_medico`
  legado: se limpian ("0512" -> 512), se buscan en `LegacyMedico.no_medico` y
  se toma `medico_actual`. Sin legado o sin `medico_actual` quedan sin resolver.
  (El COMMENT del dump en `cd_medicoalta`, "CAT_USUARIOS DBSIIM", es erroneo:
  verificado 537/537 contra `no_medico`.)

Uso (correr DESPUES de cargar `legacy_medico` y enlazar `medico_actual`):

    python manage.py resolve_hsp_doctor_codes             # dry-run (default)
    python manage.py resolve_hsp_doctor_codes --execute   # aplica

Solo transiciona NULL -> valor, no genera HospitalAdmissionRevision y deja un
AuditoriaEvento de Sistema por campo. Es idempotente.
"""
from django.core.management.base import BaseCommand

from apps.hospitalizacion.uses_case import hospital_admission_usecase

_LABELS = {
    "admitting_doctor": "admitting_doctor (medico de ingreso)",
    "discharge_doctor": "discharge_doctor (medico de alta)",
}


class Command(BaseCommand):
    help = (
        "Resuelve admitting_doctor / discharge_doctor de hospitalizacion desde "
        "sus codigos legados (no_medico) via LegacyMedico.medico_actual. "
        "Dry-run por defecto."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica los cambios. Sin este flag solo reporta (dry-run).",
        )

    def handle(self, *args, **options):
        execute = options["execute"]
        if execute:
            report = hospital_admission_usecase.resolve_pending_doctors()
            self.stdout.write(self.style.SUCCESS("EJECUTADO"))
        else:
            report = hospital_admission_usecase.preview_pending_doctors()
            self.stdout.write(self.style.WARNING("DRY-RUN: no se escribio nada (usar --execute)"))

        verbo = "resueltos" if execute else "se resolverian"
        for field, counts in report.items():
            self.stdout.write(
                f"{_LABELS.get(field, field)}: pendientes={counts['pending']} "
                f"{verbo}={counts['resolved']} sin_resolver={counts['unresolved']}"
            )
