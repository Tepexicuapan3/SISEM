"""
seed_farmacia_almacenes -- bootstrap idempotente de sdd/dispensacion-farmacia:

1. Un `Almacen(tipo=FARMACIA)` por `CatCentroAtencion` activo.
2. La categoria/unidad genericas para los `CatInsumo` que este comando crea.
3. Un `MedicamentoInsumo` (factor_conversion=1, permite_fraccion=True) por
   cada `Medicamentos` activo que todavia no tenga mapeo activo -- crea (o
   reusa por codigo determinista) el `CatInsumo` correspondiente.

Todo via `get_or_create`: correr el comando N veces no duplica nada (ver
sdd/dispensacion-farmacia/tasks, fase 5, tarea 5.1).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.almacen_insumos.models.catalogos import (
    Almacen,
    CatCategoriaInsumo,
    CatInsumo,
    CatUnidadMedida,
)
from apps.almacen_insumos.models.farmacia import MedicamentoInsumo
from apps.catalogos.models import CatCentroAtencion, Medicamentos

_CATEGORIA_NOMBRE = "Medicamentos"
_CATEGORIA_DESCRIPCION = (
    "Insumos de farmacia generados automaticamente a partir del catalogo "
    "de medicamentos (seed_farmacia_almacenes)."
)
_UNIDAD_NOMBRE = "Unidad"
_UNIDAD_ABREVIACION = "u"


class Command(BaseCommand):
    help = (
        "Bootstrap idempotente de dispensacion de farmacia: crea un Almacen "
        "tipo FARMACIA por centro de atencion activo, la categoria/unidad "
        "genericas de insumos de farmacia, y un MedicamentoInsumo (factor=1) "
        "por cada medicamento activo sin mapeo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No escribe en la base de datos, solo reporta que haria.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        with transaction.atomic():
            summary = self._run()
            if dry_run:
                transaction.set_rollback(True)

        self._report(summary, dry_run=dry_run)

    # ------------------------------------------------------------------
    def _run(self) -> dict:
        almacenes_creados = self._seed_almacenes()
        categoria, unidad = self._seed_categoria_y_unidad()
        insumos_creados, mapeos_creados = self._seed_mapeos(categoria, unidad)

        return {
            "almacenesCreados": almacenes_creados,
            "insumosCreados": insumos_creados,
            "mapeosCreados": mapeos_creados,
        }

    def _seed_almacenes(self) -> int:
        creados = 0
        for centro in CatCentroAtencion.objects.filter(is_active=True):
            _, fue_creado = Almacen.objects.get_or_create(
                tipo=Almacen.Tipo.FARMACIA,
                id_centro_atencion=centro,
                defaults={"nombre": f"Farmacia {centro.name}"},
            )
            if fue_creado:
                creados += 1
        return creados

    def _seed_categoria_y_unidad(self):
        categoria, _ = CatCategoriaInsumo.objects.get_or_create(
            nombre=_CATEGORIA_NOMBRE,
            defaults={"descripcion": _CATEGORIA_DESCRIPCION},
        )
        unidad, _ = CatUnidadMedida.objects.get_or_create(
            nombre=_UNIDAD_NOMBRE,
            defaults={"abreviacion": _UNIDAD_ABREVIACION},
        )
        return categoria, unidad

    def _seed_mapeos(self, categoria, unidad) -> tuple[int, int]:
        insumos_creados = 0
        mapeos_creados = 0

        medicamentos_mapeados = set(
            MedicamentoInsumo.objects.filter(is_active=True).values_list(
                "medicamento_id", flat=True,
            )
        )

        for medicamento in Medicamentos.objects.filter(is_active=True):
            if medicamento.pk in medicamentos_mapeados:
                continue

            codigo = f"MED-{medicamento.pk}"
            insumo, insumo_creado = CatInsumo.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "nombre": medicamento.name,
                    "id_categoria": categoria,
                    "id_unidad": unidad,
                },
            )
            if insumo_creado:
                insumos_creados += 1

            _, mapeo_creado = MedicamentoInsumo.objects.get_or_create(
                medicamento=medicamento,
                defaults={
                    "insumo": insumo,
                    "factor_conversion": 1,
                    "permite_fraccion": True,
                },
            )
            if mapeo_creado:
                mapeos_creados += 1

        return insumos_creados, mapeos_creados

    # ------------------------------------------------------------------
    def _report(self, summary: dict, *, dry_run: bool) -> None:
        prefijo = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefijo}[seed_farmacia_almacenes] "
                f"almacenes={summary['almacenesCreados']} "
                f"insumos={summary['insumosCreados']} "
                f"mapeos={summary['mapeosCreados']}"
            )
        )
