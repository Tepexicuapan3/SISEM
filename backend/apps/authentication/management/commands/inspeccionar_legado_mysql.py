from __future__ import annotations

import json

import pymysql
from django.core.management.base import BaseCommand

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Inspecciona (solo lectura) un esquema MySQL legado: lista tablas, conteo de filas, "
        "columnas y, si existe una columna de fecha de actualizacion, su valor maximo. "
        "No escribe nada en el legado ni en SISEM. Es el inventario previo obligatorio antes "
        "de escribir cualquier comando de migracion real (no se debe adivinar el esquema)."
    )

    def add_arguments(self, parser):
        self.add_legacy_mysql_arguments(parser)
        parser.add_argument(
            "--tabla",
            action="append",
            dest="tablas",
            default=None,
            help="Limitar la inspeccion a estas tablas (repetir la bandera para varias). Sin esto, inspecciona todas.",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Ruta de archivo .json donde ademas escribir el resultado.",
        )

    def handle(self, *args, **options):
        conn = self.conectar_legado(options)

        try:
            nombres_tabla = options["tablas"] or self._listar_nombres_tabla(conn, options["database"])
            reporte = {
                "database": options["database"],
                "tablas": [self._inspeccionar_tabla(conn, options["database"], t) for t in nombres_tabla],
            }
        finally:
            conn.close()

        self.stdout.write(json.dumps(reporte, indent=2, ensure_ascii=False, default=str))

        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as fh:
                json.dump(reporte, fh, indent=2, ensure_ascii=False, default=str)
            self.stdout.write(self.style.SUCCESS(f"Resultado también escrito en {options['output']}"))

    def _listar_nombres_tabla(self, conn, database: str) -> list[str]:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name",
                (database,),
            )
            return [row["table_name"] for row in cursor.fetchall()]

    def _inspeccionar_tabla(self, conn, database: str, tabla: str) -> dict:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable, column_key
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (database, tabla),
            )
            columnas = cursor.fetchall()

            columnas_fecha = [
                c["column_name"]
                for c in columnas
                if c["data_type"] in ("datetime", "timestamp", "date")
            ]

            try:
                cursor.execute(f"SELECT COUNT(*) AS total FROM `{tabla}`")
                total_filas = cursor.fetchone()["total"]
            except pymysql.err.MySQLError as exc:
                total_filas = None
                error_conteo = str(exc)
            else:
                error_conteo = None

            ultima_actualizacion = None
            columna_fecha_usada = None
            for columna in columnas_fecha:
                try:
                    cursor.execute(f"SELECT MAX(`{columna}`) AS max_fecha FROM `{tabla}`")
                    valor = cursor.fetchone()["max_fecha"]
                    if valor is not None:
                        ultima_actualizacion = valor
                        columna_fecha_usada = columna
                        break
                except pymysql.err.MySQLError:
                    continue

        return {
            "tabla": tabla,
            "total_filas": total_filas,
            "error_conteo": error_conteo,
            "columnas": [
                {
                    "nombre": c["column_name"],
                    "tipo": c["data_type"],
                    "nullable": c["is_nullable"] == "YES",
                    "llave": c["column_key"] or None,
                }
                for c in columnas
            ],
            "ultima_actualizacion": ultima_actualizacion,
            "columna_fecha_usada": columna_fecha_usada,
        }
