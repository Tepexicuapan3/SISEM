from __future__ import annotations

import os

import pymysql
import pymysql.cursors
from django.core.management.base import CommandError


class LegacyMysqlCommandMixin:
    """Mixin para management commands que leen de un MySQL legado (java-main).

    Centraliza el manejo de credenciales via variables de entorno LEGACY_MYSQL_*
    (o banderas explicitas que las sobreescriben) y la conexion pymysql, para que
    los comandos de migracion (escriben en SISEM) y de inspeccion (solo lectura)
    no dupliquen el mismo parseo/validacion.
    """

    def add_legacy_mysql_arguments(self, parser, *, require_database: bool = True) -> None:
        parser.add_argument("--host", default=os.getenv("LEGACY_MYSQL_HOST"))
        parser.add_argument("--port", type=int, default=int(os.getenv("LEGACY_MYSQL_PORT", "3306")))
        parser.add_argument("--user", default=os.getenv("LEGACY_MYSQL_USER"))
        parser.add_argument("--password", default=os.getenv("LEGACY_MYSQL_PASSWORD"))
        parser.add_argument("--database", default=os.getenv("LEGACY_MYSQL_DATABASE"))
        self._legacy_mysql_require_database = require_database

    def conectar_legado(self, options: dict):
        requeridos = ["host", "user", "password"]
        if getattr(self, "_legacy_mysql_require_database", True):
            requeridos.append("database")

        faltantes = [r for r in requeridos if not options.get(r)]
        if faltantes:
            listado = ", ".join(f"--{r} (o LEGACY_MYSQL_{r.upper()})" for r in faltantes)
            raise CommandError(f"Faltan credenciales del legado: {listado}.")

        return pymysql.connect(
            host=options["host"],
            port=options["port"],
            user=options["user"],
            password=options["password"],
            database=options.get("database"),
            cursorclass=pymysql.cursors.DictCursor,
        )
