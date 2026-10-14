"""
Aplica las ausencias de médico YA registradas a sus horarios.

Antes de este cambio, registrar una ausencia (vacaciones, hora de comida,
etc.) no bloqueaba los horarios ya generados: el portal los seguía
ofreciendo. Las ausencias nuevas se aplican solas; este comando cubre las
que ya existían. Se corre una vez después del deploy.

Por cada ausencia activa que no terminó: bloquea los horarios futuros libres
que cubre y lista las citas ya agendadas dentro de ella. Las citas NO se
cancelan: recepción las reprograma.

Idempotente (un horario ya bloqueado no vuelve a contarse). Correr primero
con --dry-run.
"""

from datetime import date

from django.core.management.base import BaseCommand

from apps.medicos.models import RelMedicoExcepcion
from apps.recepcion.services.bloqueo_slots_service import (
    bloquear_slots_por_excepcion,
    citas_afectadas_por_excepcion,
    slots_a_bloquear,
)


class Command(BaseCommand):
    help = (
        "Bloquea los horarios futuros que cubren las ausencias de médico ya registradas "
        "y lista las citas afectadas (no las cancela). Idempotente. --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo cuenta.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        prefix = "[dry-run] " if dry_run else ""

        excepciones = (
            RelMedicoExcepcion.objects
            .filter(is_active=True, fecha_fin__gte=date.today())
            .select_related("medico")
            .order_by("medico_id", "fecha_inicio")
        )

        total_horarios = 0
        total_citas = 0
        for exc in excepciones:
            horarios = len(slots_a_bloquear(exc)) if dry_run else bloquear_slots_por_excepcion(exc)
            citas = citas_afectadas_por_excepcion(exc)
            total_horarios += horarios
            total_citas += len(citas)
            if horarios or citas:
                self.stdout.write(
                    f"{prefix}Médico {exc.medico_id} · {exc.get_tipo_display()} "
                    f"{exc.fecha_inicio}..{exc.fecha_fin}: {horarios} horarios, "
                    f"{len(citas)} citas a reprogramar"
                )
                for cita in citas:
                    self.stdout.write(f"    cita {cita.folio} {cita.fecha_hora.isoformat()}")

        verbo = "se bloquearían" if dry_run else "bloqueados"
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{excepciones.count()} ausencias revisadas: {total_horarios} horarios "
            f"{verbo}, {total_citas} citas a reprogramar (no se cancelan)."
        ))
