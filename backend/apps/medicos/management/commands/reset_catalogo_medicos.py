"""
reset_catalogo_medicos -- runbook de reset del catalogo de medicos, SOLO TEST
(cambio `medicos-id-no-medico`, R10 / D9).

Vacia `cat_medicos` para reimportar el Excel con `CatMedico.id` = No. Medico
legado y deja la secuencia del id lista para que el siguiente `nextval` sea 1
(el import reajusta la secuencia con max(id)+1).

NUNCA correr contra produccion. No existe un indicador de entorno confiable en
settings (`DEBUG` tiene default True y TEST tambien puede correr con
DEBUG=False), asi que la salvaguarda es explicita: `--db-name` es obligatorio
y debe ser IGUAL al NAME de la BD configurada, y por defecto es dry-run.

Uso:

    python manage.py reset_catalogo_medicos --db-name <NAME>                 # dry-run
    python manage.py reset_catalogo_medicos --db-name <NAME> --execute       # aplica
    python manage.py reset_catalogo_medicos --db-name <NAME> --execute \\
        --purge-citas-cirugias      # ademas borra citas/cirugias de prueba

Solo ORM: sin TRUNCATE, sin DELETE crudo, sin CASCADE en SQL. Las FKs no
tienen ON DELETE en la BD (Django nunca lo emite), por eso las cascadas
(rel_medico_*, slots) solo existen en el Collector del ORM.

Pasos (una sola transaccion; cualquier error revierte todo):
  1. Conteos ANTES.
  2. Si hay citas_medicas / cir_surgery -> aborta salvo `--purge-citas-cirugias`
     (borra por ORM; cascadea diagnosticos/cancelaciones de cirugia).
  3. NULL en las FKs PROTECT nullables: hsp_admission (ingreso/alta),
     revisiones (previous_*) y consumos de kardex. Los `*_code_legacy` crudos
     NO se tocan: son el puente para `resolve_hsp_doctor_codes`.
  4. CatMedico.objects.all().delete() (rel_* y slots cascadean por ORM).
  5. Postgres: setval(secuencia, 1, false). SQLite: se omite.
  6. Conteos DESPUES; hsp_admission / revisiones / consumos deben conservar
     el mismo total (solo se nulearon FKs) o se revierte.

EXCEPCION DOCUMENTADA al append-only de `HospitalAdmissionRevision`: el paso 3
usa `QuerySet.update()`, que no pasa por `save()`/`delete()` (los que bloquean
la edicion). Es valida SOLO en TEST y solo sobre las FKs de medico.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError

from apps.almacen_insumos.models import ConsumoConsulta
from apps.cirugias.models import SurgerySchedule
from apps.hospitalizacion.models import HospitalAdmission, HospitalAdmissionRevision
from apps.medicos.models import (
    CatMedico,
    RelMedicoCentro,
    RelMedicoCobertura,
    RelMedicoConsultorio,
    RelMedicoEspecialidad,
    RelMedicoExcepcion,
)
from apps.recepcion.models import CitaMedica, HorarioDisponible


class ResetAbortado(CommandError):
    """Falla de una precondicion/verificacion; revierte la transaccion."""


def _contar() -> dict[str, int]:
    """Conteos de todo lo que el reset lee o muta (claves ordenadas para imprimir)."""
    return {
        "cat_medicos": CatMedico.objects.count(),
        "rel_medico_especialidad": RelMedicoEspecialidad.objects.count(),
        "rel_medico_centro": RelMedicoCentro.objects.count(),
        "rel_medico_consultorio": RelMedicoConsultorio.objects.count(),
        "rel_medico_excepcion": RelMedicoExcepcion.objects.count(),
        "rel_medico_cobertura": RelMedicoCobertura.objects.count(),
        "citas_medicas": CitaMedica.objects.count(),
        "citas_horarios_disponibles": HorarioDisponible.objects.count(),
        "cir_surgery": SurgerySchedule.objects.count(),
        "hsp_admission": HospitalAdmission.objects.count(),
        "hsp_admission (con medico ingreso/alta)": HospitalAdmission.objects.filter(
            Q(admitting_doctor__isnull=False) | Q(discharge_doctor__isnull=False)
        ).count(),
        "hsp_admission_revision": HospitalAdmissionRevision.objects.count(),
        "hsp_admission_revision (con previous_* medico)": HospitalAdmissionRevision.objects.filter(
            Q(previous_admitting_doctor__isnull=False)
            | Q(previous_discharge_doctor__isnull=False)
        ).count(),
        "almacen_consumos_consulta": ConsumoConsulta.objects.count(),
        "almacen_consumos_consulta (con medico)": ConsumoConsulta.objects.filter(
            medico__isnull=False
        ).count(),
    }


# Totales que NO pueden cambiar: el reset solo nulea FKs en estas tablas.
_INVARIANTES = (
    "hsp_admission",
    "hsp_admission_revision",
    "almacen_consumos_consulta",
)


class Command(BaseCommand):
    help = (
        "SOLO TEST. Vacia cat_medicos por ORM (nulea FKs PROTECT de "
        "hospitalizacion/kardex) y reinicia la secuencia del id. Dry-run por "
        "defecto; requiere --db-name igual al NAME de la BD."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--db-name",
            required=True,
            help="Nombre de la BD; debe ser IGUAL a DATABASES['default']['NAME'].",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica los cambios. Sin este flag solo reporta (dry-run).",
        )
        parser.add_argument(
            "--purge-citas-cirugias",
            action="store_true",
            help=(
                "Borra por ORM las citas_medicas y cir_surgery existentes (datos "
                "de prueba). Sin este flag el reset aborta si hay alguna."
            ),
        )

    def handle(self, *args, **options):
        real_name = str(connection.settings_dict["NAME"])
        if options["db_name"] != real_name:
            raise CommandError(
                f"--db-name '{options['db_name']}' no coincide con la BD configurada "
                f"'{real_name}'. Abortado sin tocar nada."
            )

        execute = options["execute"]
        purge = options["purge_citas_cirugias"]

        antes = _contar()
        self._imprimir("ANTES", antes)

        hay_citas_cirugias = bool(antes["citas_medicas"] or antes["cir_surgery"])
        if hay_citas_cirugias and not purge:
            msg = (
                f"Hay citas_medicas={antes['citas_medicas']} / cir_surgery="
                f"{antes['cir_surgery']} y estan protegidas por PROTECT. Usar "
                "--purge-citas-cirugias SOLO si son datos de prueba."
            )
            if execute:
                raise ResetAbortado(msg + " Abortado sin tocar nada.")
            self.stdout.write(self.style.WARNING("DRY-RUN: --execute abortaria. " + msg))

        if not execute:
            self.stdout.write(
                self.style.WARNING("DRY-RUN: no se escribio nada (usar --execute).")
            )
            self._plan(antes, purge)
            return

        try:
            with transaction.atomic():
                despues, purgados = self._ejecutar(antes, purge)
        except ProtectedError as exc:
            raise ResetAbortado(
                "Otra tabla protege filas de cat_medicos (PROTECT no contemplado en "
                f"el runbook). Se revirtio todo. Detalle: {exc}"
            ) from exc

        self._imprimir("DESPUES", despues)
        if purge:
            self.stdout.write(
                f"Purgado por ORM: citas_medicas={purgados['citas']} "
                f"cir_surgery={purgados['cirugias']}"
            )
        self.stdout.write(self.style.SUCCESS("EJECUTADO"))
        self._siguientes_pasos()

    # -- pasos ------------------------------------------------------------

    def _ejecutar(self, antes, purge):
        purgados = {"citas": 0, "cirugias": 0}

        if purge:
            # ORM (Collector): cascadea slots->cita SET_NULL, diagnosticos y
            # cancelaciones de cirugia, notificaciones de cita.
            purgados["cirugias"] = antes["cir_surgery"]
            purgados["citas"] = antes["citas_medicas"]
            SurgerySchedule.objects.all().delete()
            CitaMedica.objects.all().delete()

        # EXCEPCION TEST-only al append-only de las revisiones: update() no
        # pasa por save()/delete(). Los *_code_legacy NO se tocan.
        HospitalAdmission.objects.filter(
            Q(admitting_doctor__isnull=False) | Q(discharge_doctor__isnull=False)
        ).update(admitting_doctor=None, discharge_doctor=None)
        HospitalAdmissionRevision.objects.filter(
            Q(previous_admitting_doctor__isnull=False)
            | Q(previous_discharge_doctor__isnull=False)
        ).update(previous_admitting_doctor=None, previous_discharge_doctor=None)
        ConsumoConsulta.objects.filter(medico__isnull=False).update(medico=None)

        CatMedico.objects.all().delete()

        self._reiniciar_secuencia()

        despues = _contar()
        for clave in _INVARIANTES:
            if despues[clave] != antes[clave]:
                raise ResetAbortado(
                    f"El total de {clave} cambio ({antes[clave]} -> {despues[clave]}); "
                    "solo debian nulearse FKs. Se revirtio todo."
                )
        if despues["cat_medicos"] != 0:
            raise ResetAbortado("cat_medicos no quedo vacia. Se revirtio todo.")
        return despues, purgados

    def _reiniciar_secuencia(self):
        """setval(seq, 1, false): el siguiente nextval devuelve 1. Solo Postgres."""
        if connection.vendor != "postgresql":
            self.stdout.write("Secuencia: omitida (el motor no es PostgreSQL).")
            return
        with connection.cursor() as cur:
            cur.execute("SELECT pg_get_serial_sequence('cat_medicos', 'id')")
            seq = cur.fetchone()[0]
            if not seq:
                raise ResetAbortado(
                    "cat_medicos.id no tiene secuencia asociada (ver migracion 0011). "
                    "Se revirtio todo."
                )
            cur.execute("SELECT setval(%s, 1, false)", [seq])
        self.stdout.write(f"Secuencia {seq} reiniciada (proximo nextval = 1).")

    # -- salida -----------------------------------------------------------

    def _plan(self, antes, purge):
        self.stdout.write("Se haria, en una sola transaccion:")
        if purge:
            self.stdout.write(
                f"  - borrar por ORM cir_surgery={antes['cir_surgery']} y "
                f"citas_medicas={antes['citas_medicas']}"
            )
        self.stdout.write(
            "  - NULL en hsp_admission (ingreso/alta), revisiones (previous_*) y "
            "kardex medico; *_code_legacy intactos"
        )
        self.stdout.write(f"  - borrar por ORM cat_medicos ({antes['cat_medicos']} filas) y rel_*/slots en cascada")
        self.stdout.write("  - setval de la secuencia del id a 1 (solo PostgreSQL)")
        self.stdout.write("  - verificar que hsp_admission / revisiones / consumos conservan su total")

    def _imprimir(self, titulo, conteos):
        self.stdout.write(f"--- Conteos {titulo} ---")
        for clave, valor in conteos.items():
            self.stdout.write(f"  {clave}: {valor}")

    def _siguientes_pasos(self):
        self.stdout.write(
            "\nSiguientes pasos:\n"
            "  1. Importar el Excel de medicos desde la UI (Medicos > Importar).\n"
            "  2. python manage.py resolve_hsp_doctor_codes            (dry-run)\n"
            "     python manage.py resolve_hsp_doctor_codes --execute\n"
            "  3. Verificar en SQL:\n"
            "       SELECT count(*), max(id) FROM cat_medicos;\n"
            "         -> esperado 2709 | 2726 (el legado tiene 2709 filas con huecos,\n"
            "            NO 2726 | 2726)\n"
            "       SELECT pg_get_serial_sequence('cat_medicos','id');\n"
            "  4. Un alta manual de prueba debe recibir id 2727."
        )
