from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.administracion.services import oracle_ddl_service as ddl
from apps.administracion.services.sync_service import obtener_conexion_oracle


class Command(BaseCommand):
    help = (
        "Genera un script .sql con la ESTRUCTURA (sin datos) del esquema de Oracle "
        "configurado en ORACLE_CONFIG, para crear una copia de pruebas. Solo hace SELECT "
        "sobre el diccionario de datos: no escribe nada en Oracle ni en Postgres. El .sql "
        "se ejecuta a mano en la COPIA, nunca en produccion."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            required=True,
            help="Ruta del archivo .sql a generar.",
        )
        parser.add_argument(
            "--owner",
            action="append",
            dest="owners",
            default=None,
            help=(
                "Esquema a copiar (repetir la bandera para varios). Por defecto, el "
                "usuario Oracle configurado."
            ),
        )
        parser.add_argument(
            "--sin-sinonimos",
            action="store_true",
            help="No incluir las tablas a las que apuntan los sinonimos privados del usuario.",
        )
        parser.add_argument("--sin-indices", action="store_true", help="No generar indices.")
        parser.add_argument("--sin-foraneas", action="store_true", help="No generar llaves foraneas.")

    def handle(self, *args, **options):
        try:
            conn = obtener_conexion_oracle()
        except Exception as exc:
            raise CommandError(f"No se pudo conectar a Oracle: {exc}") from exc

        try:
            usuario = ddl.usuario_actual(conn)
            version = ddl.version_oracle(conn) or "desconocida"
            owners = [o.strip().upper() for o in (options["owners"] or [usuario]) if o.strip()]
            esquema = ddl.leer_esquema(conn, owners, incluir_sinonimos=not options["sin_sinonimos"])
        finally:
            conn.close()

        if not esquema.tablas:
            raise CommandError(
                f"No se encontraron tablas para {', '.join(owners)}: el esquema no existe o el "
                f"usuario {usuario} no tiene visibilidad sobre el."
            )

        encabezado = "\n".join([
            "-- Estructura del Oracle de SERMED para una COPIA DE PRUEBAS. Sin datos.",
            f"-- Generado por manage.py generar_ddl_oracle el {timezone.localtime():%Y-%m-%d %H:%M}",
            f"-- Esquema(s) de origen: {', '.join(owners)} (usuario {usuario}, Oracle {version}).",
            "-- NO EJECUTAR EN PRODUCCION: correrlo conectado al usuario de la copia.",
            "-- Las tablas se crean en el esquema del usuario que ejecuta el script.",
        ])
        script = ddl.generar_script(
            esquema,
            encabezado=encabezado,
            incluir_indices=not options["sin_indices"],
            incluir_foraneas=not options["sin_foraneas"],
        )
        with open(options["output"], "w", encoding="utf-8") as fh:
            fh.write(script)

        restricciones = ddl.copiables(esquema)
        conteo = {tipo: sum(1 for r in restricciones if r.tipo == tipo) for tipo in "PURC"}
        self.stdout.write(
            f"Oracle {version} | Tablas: {len(esquema.tablas)} (por sinonimo: {len(esquema.sinonimos)}) | "
            f"PK: {conteo['P']} UK: {conteo['U']} FK: {conteo['R']} CHECK: {conteo['C']} | "
            f"Indices leidos: {len(esquema.indices)}"
        )
        if esquema.no_copiados:
            self.stdout.write(
                "No copiado: " + ", ".join(f"{t}={n}" for t, n in sorted(esquema.no_copiados.items()))
            )
        self.stdout.write(self.style.SUCCESS(f"Script escrito en {options['output']}"))
