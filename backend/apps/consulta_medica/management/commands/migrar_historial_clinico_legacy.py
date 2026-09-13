"""
Migra el historial clinico general desde el legado (MySQL, tabla
`his_clinica`) a `consulta_medica.ClinicalHistory`.

Mapeo de columnas reconstruido leyendo el JOIN real usado por el legado en
`usuarios/clinicam/his-clinico.jsp` (java-main) -- no hay dump con
`CREATE TABLE` de `his_clinica` disponible, así que este es el mapeo mejor
disponible hasta poder correr `inspeccionar_legado_mysql --tabla his_clinica`
contra el servidor real y confirmarlo columna por columna.

IMPORTANTE -- resolución de catálogos por NOMBRE, no por id crudo:
los ids de cat_ocupacion/cat_escolaridad/cat_edocivil/cat_religion/
cat_residencia del legado NO tienen por qué coincidir con los ids de los
catálogos ya sembrados en SISEM (fueron cargados de forma independiente).
Copiar el id crudo apuntaría silenciosamente al catálogo equivocado. Por
eso este comando repite el mismo JOIN contra los catálogos del legado que
usa el JSP para obtener la DESCRIPCIÓN, y resuelve esa descripción contra
el catálogo real de SISEM por nombre (case-insensitive, sin espacios
extra). Lo que no matchea se reporta y se deja NULL -- nunca se adivina.
"""

from __future__ import annotations

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin
from apps.catalogos.models import EdoCivil, Escolaridad, Ocupaciones, Religion, TipoResidencia
from apps.consulta_medica.models import ClinicalHistory
from django.core.management.base import BaseCommand

# (columna FK en ClinicalHistory, columna de descripcion resuelta por el JOIN
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
        a.no_exp, a.tp_paciente, a.fe_hisclin,
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


def _norm(value) -> str:
    return (value or "").strip().casefold()


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Migra his_clinica (MySQL legado) a consulta_medica.ClinicalHistory. "
        "Los catalogos se resuelven por NOMBRE (no por id crudo -- ver docstring "
        "del archivo). --dry-run no escribe nada."
    )

    def add_arguments(self, parser):
        self.add_legacy_mysql_arguments(parser)
        parser.add_argument("--dry-run", action="store_true",
                            help="No escribe nada, solo reporta que haria.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Limitar cantidad de filas del legado (para pruebas).")

    def handle(self, *args, **options):
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

        catalogo_por_nombre = {
            fk_field: {_norm(obj.name): obj.id for obj in modelo.objects.all()}
            for fk_field, _col, modelo in _CATALOGOS
        }

        creados = 0
        actualizados = 0
        catalogos_sin_match: dict[str, set[str]] = {fk: set() for fk, _c, _m in _CATALOGOS}
        errores: list[str] = []

        for row in rows:
            no_exp = (row.get("no_exp") or "").strip()
            if not no_exp:
                errores.append("Fila sin no_exp, omitida.")
                continue

            try:
                pk_num = int(row.get("tp_paciente") or 0)
            except (TypeError, ValueError):
                errores.append(f"no_exp={no_exp}: tp_paciente invalido ({row.get('tp_paciente')!r}), omitida.")
                continue

            defaults = {
                "phone": row.get("ds_telefono") or None,
                "family_history": row.get("ds_antecedentes") or None,
                "current_illness": row.get("ds_padecimiento") or None,
                "systems_review": row.get("ds_orgapasis") or None,
                "head_exam": row.get("ds_cabeza") or None,
                "neck_exam": row.get("ds_cuello") or None,
                "chest_exam": row.get("ds_torax") or None,
                "abdomen_exam": row.get("ds_abdomen") or None,
                "genitals_exam": row.get("ds_genitales") or None,
                "limbs_exam": row.get("ds_miembros") or None,
                "diagnostic_management": row.get("ds_mdiagnostico") or None,
                "therapeutic_management": row.get("ds_mterapeutico") or None,
                "allergies": row.get("ds_alergias") or None,
            }

            for fk_field, col, _modelo in _CATALOGOS:
                descripcion = row.get(col)
                if not descripcion:
                    defaults[fk_field] = None
                    continue
                resuelto = catalogo_por_nombre[fk_field].get(_norm(descripcion))
                if resuelto is None:
                    catalogos_sin_match[fk_field].add(descripcion)
                defaults[fk_field] = resuelto

            if options["dry_run"]:
                existe = ClinicalHistory.objects.filter(no_exp=no_exp, pk_num=pk_num).exists()
                if existe:
                    actualizados += 1
                else:
                    creados += 1
                continue

            _, created = ClinicalHistory.objects.update_or_create(
                no_exp=no_exp, pk_num=pk_num, defaults=defaults,
            )
            if created:
                creados += 1
                fe_hisclin = row.get("fe_hisclin")
                if fe_hisclin:
                    # auto_now_add ya puso "ahora" -- se corrige aparte para
                    # preservar la fecha real del historial legado.
                    ClinicalHistory.objects.filter(
                        no_exp=no_exp, pk_num=pk_num,
                    ).update(created_at=fe_hisclin)
            else:
                actualizados += 1

        prefix = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Creados: {creados}, Actualizados: {actualizados}, Errores: {len(errores)}"
        ))
        for err in errores:
            self.stdout.write(self.style.WARNING(f"  - {err}"))

        for fk_field, valores in catalogos_sin_match.items():
            if valores:
                self.stdout.write(self.style.WARNING(
                    f"Sin match en catalogo SISEM para '{fk_field}' (quedaron NULL): "
                    f"{sorted(valores)}"
                ))
