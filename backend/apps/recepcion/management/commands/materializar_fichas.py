"""
Crea las fichas automáticas de las citas de hoy (las que no son del portal).
Es lo mismo que hace la tarea ``recepcion.tasks.materializar_fichas``; sirve
para desarrollo, donde no corre Celery. Se puede correr varias veces.
"""

from django.core.management.base import BaseCommand

from apps.recepcion.uses_case.materializar_fichas_usecase import materializar_fichas_del_dia


class Command(BaseCommand):
    help = "Crea las fichas en espera de las citas de hoy que no son del portal."

    def handle(self, *args, **options):
        resumen = materializar_fichas_del_dia()
        self.stdout.write(f"Fichas creadas {resumen['fecha']}: {resumen['creadas']}")
        for omitida in resumen["omitidas"]:
            self.stdout.write(f"  Sin ficha {omitida['folio']}: {omitida['motivo']}")
