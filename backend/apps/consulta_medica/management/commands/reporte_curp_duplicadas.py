"""
Reporte de CURP repetidas en cns_paciente (documento "Historia Clinica
Unificada", 5.1). Solo lectura.

El documento pide CURP unica. La restriccion todavia no existe porque SERMED
tiene CURP repetidas: la misma persona con varios NO_EXP (reingresos) o con
dos papeles (titular y familiar). Cada grupo de este reporte es un candidato
a fusion: un solo paciente con varios identificadores. Cuando el reporte
salga vacio se puede agregar la restriccion UNIQUE (curp) WHERE curp IS NOT NULL.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.consulta_medica.models import Patient


class Command(BaseCommand):
    help = "Lista las CURP que estan en mas de un paciente (candidatos a fusion). No escribe nada."

    def handle(self, *args, **options):
        repetidas = (
            Patient.objects.exclude(curp__isnull=True).exclude(curp="")
            .values("curp").annotate(total=Count("id_patient")).filter(total__gt=1)
            .order_by("-total", "curp")
        )
        curps = [fila["curp"] for fila in repetidas]
        if not curps:
            self.stdout.write(self.style.SUCCESS("Sin CURP repetidas: se puede agregar la restriccion UNIQUE."))
            return

        pacientes = (
            Patient.objects.filter(curp__in=curps)
            .order_by("curp", "no_exp", "pk_num")
            .values("curp", "id_patient", "no_exp", "pk_num", "legacy_family_code",
                    "paternal_surname", "maternal_surname", "first_name", "curp_source")
        )
        self.stdout.write(self.style.WARNING(f"CURP repetidas: {len(curps)}"))
        actual = None
        for paciente in pacientes:
            if paciente["curp"] != actual:
                actual = paciente["curp"]
                self.stdout.write(f"\n{actual}")
            nombre = " ".join(
                parte for parte in (paciente["paternal_surname"], paciente["maternal_surname"],
                                    paciente["first_name"]) if parte
            ) or "(sin nombre copiado)"
            self.stdout.write(
                f"  id_paciente={paciente['id_patient']} no_exp={paciente['no_exp']} "
                f"pk_num={paciente['pk_num']} cd_familiar={paciente['legacy_family_code']} "
                f"origen={paciente['curp_source'] or '-'} {nombre}"
            )
