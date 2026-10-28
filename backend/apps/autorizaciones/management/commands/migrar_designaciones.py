"""
F8: pasa las designaciones vigentes de la pantalla vieja (cat_designacion_autorizador)
al modulo de autorizadores. Sin --aplicar solo muestra el reporte; se puede correr
las veces que haga falta: lo ya migrado se reporta como YA_MIGRADA.

Ejemplos:
    python manage.py migrar_designaciones
    python manage.py migrar_designaciones --aplicar
"""
import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.administracion.models.auditoria_evento import AuditoriaEvento
from apps.autorizaciones.uses_case.migracion_designaciones_use_case import (
    Estado,
    migrar_designaciones,
)


def _auditoria(id_ejecucion):
    # Sin request HTTP no hay ip ni agente: el id de ejecucion agrupa los eventos.
    def registrar(accion, id_recurso, antes, despues):
        AuditoriaEvento.objects.create(
            fch_evento=timezone.now(),
            request_id=id_ejecucion,
            accion=accion,
            recurso_tipo="autorizador",
            recurso_id=id_recurso,
            resultado=AuditoriaEvento.Resultado.SUCCESS,
            datos_antes=antes,
            datos_despues=despues,
            meta={"module": "autorizaciones", "origen": "migrar_designaciones"},
        )

    return registrar


class Command(BaseCommand):
    help = "Migra las designaciones de autorizadores al modulo nuevo (vista previa sin --aplicar)."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Escribe los cambios.")

    def handle(self, *args, **options):
        id_ejecucion = str(uuid.uuid4())
        reporte = migrar_designaciones(
            aplicar=options["aplicar"],
            hoy=timezone.localdate(),
            auditoria=_auditoria(id_ejecucion),
            identificador_peticion=f"migrar_designaciones:{id_ejecucion}",
        )

        self.stdout.write("APLICADO" if reporte.aplicado else "VISTA PREVIA (nada se escribio; use --aplicar)")
        self.stdout.write(f"Ejecucion: {id_ejecucion}")
        self.stdout.write("designacion | usuario | tipo viejo -> nuevo | estado | motivo | autorizador")
        for r in reporte.resultados:
            self.stdout.write(
                f"{r.id_designacion} | {r.id_usuario} | {r.clave_vieja} -> {r.clave_nueva or '-'} | "
                f"{r.estado.value} | {r.motivo or '-'} | {r.id_autorizador or '-'}"
            )
        self.stdout.write(
            "Totales: "
            + ", ".join(f"{estado.value}={reporte.total(estado)}" for estado in Estado)
        )
