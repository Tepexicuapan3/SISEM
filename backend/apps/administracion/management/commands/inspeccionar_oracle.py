from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.administracion.services.sync_service import obtener_conexion_oracle


class Command(BaseCommand):
    help = (
        "Inspecciona (solo lectura) el esquema de Oracle configurado en ORACLE_CONFIG: "
        "lista tablas del usuario, o columnas/tipos de una o varias tablas puntuales. "
        "No escribe nada en Oracle ni en Postgres. Pensado para confirmar antes de migrar "
        "si una tabla/columna existe realmente (p. ej. si cat_empleados ya tiene CURP) "
        "en vez de asumirlo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tabla",
            action="append",
            dest="tablas",
            default=None,
            help=(
                "Nombre de tabla a inspeccionar (repetir la bandera para varias). "
                "Sin este argumento, lista todas las tablas del usuario Oracle configurado."
            ),
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Ruta de archivo .json donde además escribir el resultado.",
        )

    def handle(self, *args, **options):
        tablas = options["tablas"]
        output_path = options["output"]

        try:
            conn = obtener_conexion_oracle()
        except Exception as exc:
            raise CommandError(f"No se pudo conectar a Oracle: {exc}") from exc

        try:
            resultado = self._listar_tablas(conn) if not tablas else self._describir_tablas(conn, tablas)
        finally:
            conn.close()

        self.stdout.write(json.dumps(resultado, indent=2, ensure_ascii=False, default=str))

        if output_path:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(resultado, fh, indent=2, ensure_ascii=False, default=str)
            self.stdout.write(self.style.SUCCESS(f"Resultado también escrito en {output_path}"))

    def _listar_tablas(self, conn) -> dict:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT table_name, num_rows FROM user_tables ORDER BY table_name"
            )
            filas = cursor.fetchall()
        finally:
            cursor.close()

        return {
            "tablas": [
                {"nombre": nombre, "num_rows_estimado": num_rows}
                for nombre, num_rows in filas
            ]
        }

    def _describir_tablas(self, conn, tablas: list[str]) -> dict:
        cursor = conn.cursor()
        resultado: dict = {}
        try:
            for tabla in tablas:
                cursor.execute(
                    """
                    SELECT column_name, data_type, data_length, nullable, data_default
                    FROM all_tab_columns
                    WHERE table_name = :1
                    ORDER BY column_id
                    """,
                    (tabla.upper(),),
                )
                columnas = cursor.fetchall()
                if not columnas:
                    resultado[tabla] = {
                        "existe": False,
                        "columnas": [],
                        "nota": "Sin columnas encontradas: la tabla no existe o el usuario Oracle configurado no tiene visibilidad sobre ella.",
                    }
                    continue

                resultado[tabla] = {
                    "existe": True,
                    "columnas": [
                        {
                            "nombre": nombre,
                            "tipo": tipo,
                            "longitud": longitud,
                            "nullable": nullable == "Y",
                            "default": default,
                        }
                        for nombre, tipo, longitud, nullable, default in columnas
                    ],
                }
        finally:
            cursor.close()

        return resultado
