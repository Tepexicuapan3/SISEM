from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalogos.models import CatTipoAlta, CatTipoHospitalizacion

# Valores reales de `cat_tphospi` (23 filas, todas sw_status='A') verificados
# directamente contra el dump `D:\PROYECTOS EN PRODUCCION\Dump SISEM\Dump20260903.sql`
# (`INSERT INTO cat_tphospi VALUES ...`, tabla `cd_tphospi`/`ds_tphospi`).
# Clave = legacy_code (cd_tphospi), usado por HospitalAdmission.admission_type
# para resolver `his_hospital.cd_tphospi` (change his-hospital-modelo-nom024).
TIPO_HOSPITALIZACION_LEGADO = (
    (1, "ATENCIÓN EN URGENCIAS"),
    (2, "CORTA ESTANCIA"),
    (3, "CIRUGÍA"),
    (4, "HOSPITALIZACIÓN"),
    (5, "MATERNIDAD"),
    (6, "ENDOSCOPIA"),
    (7, "PH METRIA"),
    (8, "MANOMETRIA"),
    (9, "COLONOSCOPIA"),
    (10, "CISTOSCOPIA"),
    (11, "LITOTRIPSIA"),
    (12, "INHALOTERAPIA"),
    (13, "HEMODIALISIS"),
    (14, "ESTUDIO LABORATORIO"),
    (15, "ESTUDIO GABINETE"),
    (16, "QUIMIOTERAPIA"),
    (17, "RADIOTERAPIA"),
    (18, "URODINAMIA"),
    (19, "CISTOGRAFIA"),
    (20, "COLOCACION CATETER"),
    (21, "DOBLE JJ"),
    (22, "ESTUDIO ANATOMIA PATOLOGICA"),
    (23, "CONTROL TÉRMICO"),
)

# Valores reales de `cat_tpaltas` (6 filas, todas sw_status='A'), mismo dump
# (tabla `tp_alta`/`ds_alta`). Clave = legacy_code (tp_alta), usado por
# HospitalAdmission.discharge_type para resolver `his_hospital.tp_alta`.
#
# NOTA sobre el valor 5: el dato crudo del legado es literalmente
# "ALTA POR MAXIMO BENEFICIO)" -- parentesis de cierre sin apertura, error
# de captura evidente (comparar con el valor 2, que SI balancea sus
# parentesis). Se corrige el typo tipografico aqui porque es un catalogo
# NUEVO orientado a mostrarse en SIRES; el legacy_code (la clave real del
# JOIN) se conserva intacto.
TIPO_ALTA_LEGADO = (
    (1, "ALTA VOLUNTARIA"),
    (2, "ALTA MÉDICA (POR MEJORIA Y/O CURACIÓN)"),
    (3, "ALTA POR TRASLADO A OTRA UNIDAD"),
    (4, "ALTA POR DEFUNSIÓN"),
    (5, "ALTA POR MAXIMO BENEFICIO"),
    (6, "ALTA"),
)


class Command(BaseCommand):
    help = (
        "Siembra los catalogos CatTipoHospitalizacion (23 valores, desde "
        "cat_tphospi) y CatTipoAlta (6 valores, desde cat_tpaltas) del "
        "legado (dump Dump20260903.sql), prerequisito de las FK de "
        "HospitalAdmission.admission_type/discharge_type (change "
        "his-hospital-modelo-nom024). Idempotente: usa "
        "update_or_create(legacy_code=...), se puede re-correr sin duplicar "
        "filas. Por defecto corre en modo vista previa -- pasa --confirm "
        "para ejecutar de verdad."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Ejecuta los cambios de verdad. Sin esto, solo muestra que se haria.",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]

        self.stdout.write("=== Vista previa ===")
        self._preview("CatTipoHospitalizacion (cat_tphospi)", CatTipoHospitalizacion, TIPO_HOSPITALIZACION_LEGADO)
        self._preview("CatTipoAlta (cat_tpaltas)", CatTipoAlta, TIPO_ALTA_LEGADO)

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "\nModo vista previa -- no se cambio nada. Corre con --confirm para ejecutar."
                )
            )
            return

        creados_hosp, actualizados_hosp = self._sembrar(CatTipoHospitalizacion, TIPO_HOSPITALIZACION_LEGADO)
        creados_alta, actualizados_alta = self._sembrar(CatTipoAlta, TIPO_ALTA_LEGADO)

        self.stdout.write(self.style.SUCCESS(
            f"\nCatTipoHospitalizacion: {creados_hosp} creados, {actualizados_hosp} actualizados."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"CatTipoAlta: {creados_alta} creados, {actualizados_alta} actualizados."
        ))

    def _preview(self, titulo, modelo, valores):
        existentes = set(modelo.objects.values_list("legacy_code", flat=True))
        self.stdout.write(f"\n{titulo}:")
        for legacy_code, name in valores:
            marca = "(ya existe)" if legacy_code in existentes else "(nuevo)"
            self.stdout.write(f"  - [{legacy_code}] {name} {marca}")

    def _sembrar(self, modelo, valores) -> tuple[int, int]:
        creados = 0
        actualizados = 0
        for legacy_code, name in valores:
            _, created = modelo.objects.update_or_create(
                legacy_code=legacy_code,
                defaults={"name": name},
            )
            if created:
                creados += 1
            else:
                actualizados += 1
        return creados, actualizados
