"""
Migra el historial clinico general desde el legado (MySQL, tabla
`his_clinica`) al Nucleo del paciente: PACIENTE (`consulta_medica.Patient`)
e HISTORIA_CLINICA (`consulta_medica.ClinicalHistory`).

Mapeo de columnas confirmado contra el DDL real de `his_clinica` (dump
`Dump20260903.sql`, 2026-09-14) y contra el JOIN usado por el legado en
`usuarios/clinicam/his-clinico.jsp` (java-main). `no_exp` es `int unsigned`
en el legado (no varchar) -- se castea a `str` explícitamente porque
`ClinicalHistory.no_exp` en SIRES es `CharField`.

IMPORTANTE -- resolución de catálogos por NOMBRE, no por id crudo:
los ids de cat_ocupacion/cat_escolaridad/cat_edocivil/cat_religion/
cat_residencia del legado NO tienen por qué coincidir con los ids de los
catálogos ya sembrados en SISEM (fueron cargados de forma independiente).
Copiar el id crudo apuntaría silenciosamente al catálogo equivocado. Por
eso este comando repite el mismo JOIN contra los catálogos del legado que
usa el JSP para obtener la DESCRIPCIÓN, y resuelve esa descripción contra
el catálogo real de SISEM por nombre (case-insensitive, sin espacios
extra). Lo que no matchea se reporta y se deja NULL -- nunca se adivina.

Historia clinica unificada: PACIENTE recibe los datos de la persona
(catalogos, telefono) e HISTORIA_CLINICA la cabecera (fecha/clinica/medico
de apertura). El texto acumulado (antecedentes, padecimiento, exploracion,
manejo) se parte en `HistoricalNote` por anotacion `[dd/mm/aaaa (usuario)]`,
las alergias van a `Allergy` (una por elemento, tipo "otro") y los signos
vitales a `LegacyVitalSigns` -- ver `LegacyHistoryImporter`.

Plan de migracion (seccion 8): cada ejecucion queda en cns_bitacora_migracion
(--operador, por defecto el usuario del sistema operativo) y los datos de la
ficha se aplican con la regla de conflictos de
`legacy_migration_control_service` (no pisa lo editado en SIRES, gana el
fe_hisclin mas reciente, registra cada discrepancia).
"""

from __future__ import annotations

import datetime
import re
import unicodedata

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin
from apps.catalogos.models import EdoCivil, Escolaridad, Ocupaciones, Religion, TipoResidencia
from apps.consulta_medica.models import ClinicalHistory
from apps.consulta_medica.repositories.clinical_history_repository import ClinicalHistoryRepository
from apps.consulta_medica.services.legacy_history_import_service import LegacyHistoryImporter
from apps.consulta_medica.services.legacy_migration_control_service import track_run
from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction
from django.utils import timezone

# (columna FK en Patient, columna de descripcion resuelta por el JOIN
# legado, modelo de catalogo en SISEM)
_CATALOGOS = (
    ("occupation_id", "ds_ocupacion", Ocupaciones),
    ("education_level_id", "ds_escolaridad", Escolaridad),
    ("marital_status_id", "ds_edocivil", EdoCivil),
    ("religion_id", "ds_religion", Religion),
    ("residence_type_id", "ds_residencia", TipoResidencia),
)

_QUERY = """
    SELECT
        a.no_hisclin, a.no_exp, a.tp_paciente, a.fe_hisclin, a.cd_medico, a.cd_clinica,
        a.no_peso, a.no_talla, a.no_ta, a.no_pulso, a.no_temp, a.no_resp,
        a.ds_telefono, a.ds_antecedentes, a.ds_padecimiento, a.ds_orgapasis,
        a.ds_cabeza, a.ds_cuello, a.ds_torax, a.ds_abdomen,
        a.ds_genitales, a.ds_miembros,
        a.ds_mdiagnostico, a.ds_mterapeutico, a.ds_alergias,
        b.ds_ocupacion, c.ds_escolaridad, d.ds_edocivil, e.ds_religion, f.ds_residencia
    FROM his_clinica a
    LEFT JOIN cat_ocupacion  b ON a.cd_ocupacion  = b.cd_ocupacion
    LEFT JOIN cat_escolaridad c ON a.cd_escolaridad = c.cd_escolaridad
    LEFT JOIN cat_edocivil    d ON a.cd_edocivil    = d.cd_edocivil
    LEFT JOIN cat_religion    e ON a.cd_religion    = e.cd_religion
    LEFT JOIN cat_residencia  f ON a.cd_residencia  = f.cd_residencia
"""


def _sin_acentos(text: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", text)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _norm(value) -> str:
    text = (value or "").strip().casefold()
    text = re.sub(r"\s*/\s*", "/", text)  # "a / b" -> "a/b"
    text = re.sub(r"\s*\(a\)\s*$", "", text)  # "soltero (a)" -> "soltero"
    text = re.sub(r"\s+", " ", text).strip()
    # el legado a veces omite acentos ("UNION LIBRE", "JEHOVA") -- se
    # comparan sin acentos para no depender de que el legado los haya
    # capturado bien, sin alterar el texto que se guarda en SISEM.
    return _sin_acentos(text)


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Migra his_clinica (MySQL legado) a PACIENTE + HISTORIA_CLINICA. "
        "Los catalogos se resuelven por NOMBRE (no por id crudo -- ver docstring "
        "del archivo). --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        self.add_legacy_mysql_arguments(parser)
        parser.add_argument("--dry-run", action="store_true",
                            help="No escribe nada, solo reporta que haria.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Limitar cantidad de filas del legado (para pruebas).")
        parser.add_argument("--operador", default=None,
                            help="Quien ejecuta (bitacora). Por defecto, el usuario del sistema operativo.")

    def handle(self, *args, **options):
        with track_run("migrar_historial_clinico_legacy", options=options, operator=options["operador"]) as run:
            self._migrar(run, options)

    def _migrar(self, run, options):
        conn = self.conectar_legado(options)

        try:
            with conn.cursor() as cursor:
                query = _QUERY
                if options["limit"]:
                    query += f" LIMIT {int(options['limit'])}"
                cursor.execute(query)
                rows = cursor.fetchall()
        finally:
            conn.close()

        self.stdout.write(f"Filas leidas de his_clinica: {len(rows)}")
        run.rows_read = len(rows)

        catalogo_por_nombre = {
            fk_field: {_norm(obj.name): obj.id for obj in modelo.objects.all()}
            for fk_field, _col, modelo in _CATALOGOS
        }

        creados = 0
        actualizados = 0
        importer = LegacyHistoryImporter(run=run)
        catalogos_sin_match: dict[str, set[str]] = {fk: set() for fk, _c, _m in _CATALOGOS}
        errores: list[str] = []

        for row in rows:
            no_exp = str(row.get("no_exp") or "").strip()
            if not no_exp:
                errores.append("Fila sin no_exp, omitida.")
                continue

            try:
                pk_num = int(row.get("tp_paciente") or 0)
            except (TypeError, ValueError):
                errores.append(f"no_exp={no_exp}: tp_paciente invalido ({row.get('tp_paciente')!r}), omitida.")
                continue

            # PACIENTE: datos de la persona (documento 5.1).
            patient_fields = {"phone": row.get("ds_telefono") or None}
            for fk_field, col, _modelo in _CATALOGOS:
                descripcion = row.get(col)
                if not descripcion:
                    patient_fields[fk_field] = None
                    continue
                resuelto = catalogo_por_nombre[fk_field].get(_norm(descripcion))
                if resuelto is None:
                    catalogos_sin_match[fk_field].add(descripcion)
                patient_fields[fk_field] = resuelto

            # HISTORIA_CLINICA: la apertura real del legado manda (fe_hisclin,
            # cd_clinica, cd_medico), aunque SIRES ya hubiera abierto la
            # cabecera al consultarla antes de la migracion.
            fe_hisclin = row.get("fe_hisclin")
            if isinstance(fe_hisclin, datetime.datetime):
                fe_hisclin = fe_hisclin.date()
            header_fields = {
                "opening_clinic_code": row.get("cd_clinica"),
                "opening_doctor_code": (str(row.get("cd_medico") or "").strip() or None),
            }
            if fe_hisclin:
                header_fields["opened_on"] = fe_hisclin

            if options["dry_run"]:
                existe = ClinicalHistory.objects.filter(no_exp=no_exp, pk_num=pk_num).exists()
                if existe:
                    actualizados += 1
                else:
                    creados += 1
                continue

            try:
                with transaction.atomic():
                    history, created = ClinicalHistoryRepository.get_or_create_for_patient(no_exp, pk_num)
                    importer.patient_fields(
                        history.patient, patient_fields,
                        legacy_ref=f"his_clinica:{row.get('no_hisclin')}", legacy_date=fe_hisclin,
                    )
                    ClinicalHistory.objects.filter(pk=history.pk).update(**header_fields)
                    if created and fe_hisclin:
                        # Preserva la fecha real del legado tambien en fch_alta.
                        ClinicalHistory.objects.filter(pk=history.pk).update(
                            created_at=timezone.make_aware(
                                datetime.datetime.combine(fe_hisclin, datetime.time.min)
                            ),
                        )
                    importer.import_his_clinica_row(row, no_exp=no_exp, pk_num=pk_num)
            except DatabaseError as exc:
                errores.append(f"no_exp={no_exp}: error de base de datos al guardar ({exc}), omitida.")
                continue

            if created:
                creados += 1
            else:
                actualizados += 1

        prefix = "[dry-run] " if options["dry_run"] else ""
        resumen = f"{prefix}Creados: {creados}, Actualizados: {actualizados}, Errores: {len(errores)}"
        detalle = (
            f"{prefix}Notas historicas: {importer.counters['notes']}, "
            f"Alergias importadas a cns_allergy: {importer.counters['allergies']}, "
            f"Signos vitales legado: {importer.counters['vitals']}, "
            f"Conflictos de ficha: {importer.counters['conflicts']}"
        )
        run.summary = f"{resumen}. {detalle}"
        self.stdout.write(self.style.SUCCESS(resumen))
        self.stdout.write(detalle)
        self.stdout.write(f"Bitacora de ejecucion: cns_bitacora_migracion.id_ejecucion={run.pk}")
        for err in errores:
            self.stdout.write(self.style.WARNING(f"  - {err}"))

        for fk_field, valores in catalogos_sin_match.items():
            if valores:
                self.stdout.write(self.style.WARNING(
                    f"Sin match en catalogo SISEM para '{fk_field}' (quedaron NULL): "
                    f"{sorted(valores)}"
                ))
