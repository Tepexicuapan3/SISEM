"""
Crea las fichas automáticas de las citas de hoy (las que no son del portal) y
marca no asistió las que siguen "Por llegar" pasada la tolerancia. Es lo
mismo que hacen las tareas ``recepcion.tasks.materializar_fichas`` y
``marcar_fichas_no_llegaron``; sirve para desarrollo, donde no corre Celery.
Se puede correr varias veces.
"""

from django.core.management.base import BaseCommand

from apps.recepcion.uses_case.materializar_fichas_usecase import (
    marcar_fichas_no_llegaron,
    materializar_fichas_del_dia,
)


class Command(BaseCommand):
    help = "Crea las fichas de las citas de hoy que no son del portal y marca las que no llegaron."

    def handle(self, *args, **options):
        resumen = materializar_fichas_del_dia()
        self.stdout.write(f"Fichas creadas {resumen['fecha']}: {resumen['creadas']}")
        for omitida in resumen["omitidas"]:
            self.stdout.write(f"  Sin ficha {omitida['folio']}: {omitida['motivo']}")
        no_llegaron = marcar_fichas_no_llegaron()
        self.stdout.write(f"No llegaron: {no_llegaron['marcadas']}")
