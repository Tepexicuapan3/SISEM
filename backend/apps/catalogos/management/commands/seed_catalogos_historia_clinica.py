from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import ProtectedError, RestrictedError

from apps.catalogos.models import EdoCivil, Ocupaciones, Religion, TipoResidencia

# Valores mal cargados a mano en `cat_ocupaciones` (roles de personal
# clinico) que no corresponden al proposito real del catalogo: la
# ocupacion civil del paciente que usa ClinicalHistory.occupation. Nada
# mas en el repo referencia estos nombres (confirmado via grep de
# `Ocupaciones.objects` antes de escribir este comando).
OCUPACIONES_A_BORRAR = (
    "Médico",
    "Enfermero",
    "Paramédico",
    "Técnico de laboratorio",
    "Administrativo",
)

# Ocupacion civil del paciente, tal como aparece en el legado
# `cat_ocupacion` (dump Dump20260903.sql, 2026-09-14).
OCUPACIONES_LEGADO = (
    "Comerciante",
    "Empleado",
    "Estudiante",
    "Hogar",
    "Vendedor",
    "No especifica",
)

# `cat_edocivil` legado ya tenia 5 de estos 8 sembrados en SIRES (Soltero,
# Casado, Divorciado, Viudo, Union libre) -- solo faltan estos 3.
EDOCIVIL_FALTANTES = (
    "Separado",
    "Otro",
    "No especifica",
)

# `cat_religion` legado -- catalogo vacio en SIRES, se siembra completo.
RELIGION_LEGADO = (
    "Budista",
    "Católica",
    "Cristiana",
    "Judía",
    "Protestante",
    "Sin religión",
    "Testigo de Jehová",
)

# `cat_residencia` legado -- catalogo vacio en SIRES, se siembra completo.
RESIDENCIA_LEGADO = (
    "Distrito Federal",
    "Estado de México",
)


class Command(BaseCommand):
    help = (
        "Corrige/completa los catalogos que necesita la migracion de "
        "historia clinica del legado (ver "
        "consulta_medica/management/commands/migrar_historial_clinico_legacy.py): "
        "borra los 5 valores de 'Ocupaciones' mal cargados a mano (roles de "
        "personal, no ocupacion del paciente) y siembra los valores reales del "
        "legado en Ocupaciones/EdoCivil/Religion/TipoResidencia. Por defecto "
        "corre en modo vista previa -- pasa --confirm para ejecutar de verdad."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Ejecuta los cambios de verdad. Sin esto, solo muestra que se haria.",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]

        a_borrar_qs = Ocupaciones.objects.filter(name__in=OCUPACIONES_A_BORRAR)
        encontrados_a_borrar = sorted(a_borrar_qs.values_list("name", flat=True))

        self.stdout.write("=== Vista previa ===")
        self.stdout.write("\nOcupaciones a borrar (mal cargadas, roles de personal):")
        for name in encontrados_a_borrar:
            self.stdout.write(f"  - {name}")
        if not encontrados_a_borrar:
            self.stdout.write("  (ninguna encontrada, no hay nada que borrar aqui)")

        self._preview_faltantes("Ocupaciones a sembrar", Ocupaciones, OCUPACIONES_LEGADO)
        self._preview_faltantes("EdoCivil a sembrar", EdoCivil, EDOCIVIL_FALTANTES)
        self._preview_faltantes("Religion a sembrar", Religion, RELIGION_LEGADO)
        self._preview_faltantes("TipoResidencia a sembrar", TipoResidencia, RESIDENCIA_LEGADO)

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "\nModo vista previa -- no se cambio nada. Corre con --confirm para ejecutar."
                )
            )
            return

        try:
            deleted_count, _ = a_borrar_qs.delete()
        except (ProtectedError, RestrictedError) as exc:
            blocking_objects = list(exc.args[1]) if len(exc.args) > 1 else []
            self.stderr.write(
                self.style.ERROR(
                    "Borrado de Ocupaciones abortado (nada se toco): hay registros "
                    "reales que dependen de uno de estos valores."
                )
            )
            for obj in blocking_objects[:20]:
                self.stderr.write(f"  - {obj!r}")
            return

        self.stdout.write(self.style.SUCCESS(f"\nOcupaciones borradas: {deleted_count}"))

        creados_total = 0
        creados_total += self._sembrar(Ocupaciones, OCUPACIONES_LEGADO)
        creados_total += self._sembrar(EdoCivil, EDOCIVIL_FALTANTES)
        creados_total += self._sembrar(Religion, RELIGION_LEGADO)
        creados_total += self._sembrar(TipoResidencia, RESIDENCIA_LEGADO)

        self.stdout.write(self.style.SUCCESS(f"Valores sembrados (nuevos): {creados_total}"))

    def _preview_faltantes(self, titulo, modelo, valores):
        existentes = set(modelo.objects.values_list("name", flat=True))
        self.stdout.write(f"\n{titulo}:")
        for valor in valores:
            marca = "(ya existe)" if valor in existentes else "(nuevo)"
            self.stdout.write(f"  - {valor} {marca}")

    def _sembrar(self, modelo, valores) -> int:
        creados = 0
        for valor in valores:
            _, created = modelo.objects.get_or_create(name=valor)
            if created:
                creados += 1
        return creados
