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
        parser.add_argument(
            "--tablas-sync",
            action="store_true",
            help=(
                "Modo describir para las tablas que sincroniza el boton Actualizar, con sus llaves "
                "como PK. No usa el diccionario: sirve aunque el usuario no lo vea."
            ),
        )
        parser.add_argument(
            "--describir",
            action="append",
            dest="describir",
            default=None,
            help=(
                "Modo describir: tabla (o sinonimo/vista) a describir con SELECT * ... WHERE 1 = 0, "
                "sin leer filas. Repetir la bandera para varias; se suma a --tablas-sync."
            ),
        )

    def handle(self, *args, **options):
        from apps.administracion.use_cases.expedientes.actualizar_expediente import TABLAS_SYNC

        modo_describir = options["tablas_sync"] or bool(options["describir"])
        nombres = [t.upper() for t in TABLAS_SYNC] if options["tablas_sync"] else []
        nombres += [t.strip().upper() for t in options["describir"] or [] if t.strip() and t.strip().upper() not in nombres]
        llaves = {tabla: cols for tabla, (cols, _, _) in TABLAS_SYNC.items()}

        try:
            conn = obtener_conexion_oracle()
        except Exception as exc:
            raise CommandError(f"No se pudo conectar a Oracle: {exc}") from exc

        try:
            usuario = ddl.usuario_actual(conn)
            version = ddl.version_oracle(conn) or "desconocida"
            # Sin la identidad de produccion no hay guardia, y sin guardia
            # no se entrega un script que podria correrse ahi por error.
            try:
                db_name, global_name = ddl.identidad_base(conn)
            except Exception as exc:
                raise CommandError(
                    f"No se pudo leer la identidad de la base de origen ({exc}); "
                    "no se genera el script sin la guardia contra produccion."
                ) from exc
            if modo_describir:
                owners = []
                esquema = ddl.describir_tablas(conn, nombres, llaves)
            else:
                owners = [o.strip().upper() for o in (options["owners"] or [usuario]) if o.strip()]
                esquema = ddl.leer_esquema(conn, owners, incluir_sinonimos=not options["sin_sinonimos"])
        finally:
            conn.close()

        if not esquema.tablas:
            for aviso in esquema.avisos:
                self.stderr.write(aviso)
            origen = ", ".join(nombres) if modo_describir else ", ".join(owners)
            raise CommandError(
                f"No se encontraron tablas para {origen}: no existen o el usuario {usuario} no "
                f"tiene acceso."
            )

        if modo_describir:
            origen = (
                f"-- Modo describir (SELECT * ... WHERE 1 = 0, sin leer filas) de: {', '.join(nombres)}.\n"
                "-- Sin DEFAULT, comentarios, checks ni indices. PK = llaves del sync. Textos en CHAR."
            )
        else:
            origen = f"-- Esquema(s) de origen: {', '.join(owners)}."
        encabezado = "\n".join([
            "-- Estructura del Oracle de SERMED para una COPIA DE PRUEBAS. Sin datos.",
            f"-- Generado por manage.py generar_ddl_oracle el {timezone.localtime():%Y-%m-%d %H:%M}",
            f"-- Usuario {usuario}, Oracle {version}.",
            origen,
            "-- NO EJECUTAR EN PRODUCCION: correrlo conectado al usuario de la copia.",
            "-- Ejecutarlo COMPLETO como script (F5 en SQL Developer, @archivo en sqlplus):",
            "-- la guardia de abajo solo protege si corre antes que todo lo demas.",
            "-- Las tablas se crean en el esquema del usuario que ejecuta el script.",
        ])
        script = ddl.generar_script(
            esquema,
            encabezado=encabezado,
            guardia=ddl.guardia_produccion(db_name, global_name),
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
        if modo_describir:
            self.stdout.write("Tablas descritas: " + ", ".join(sorted(t.destino for t in esquema.tablas.values())))
        if esquema.no_copiados:
            self.stdout.write(
                "No copiado: " + ", ".join(f"{t}={n}" for t, n in sorted(esquema.no_copiados.items()))
            )
        for aviso in esquema.avisos:
            self.stdout.write(self.style.WARNING(f"Aviso: {aviso}"))
        self.stdout.write(f"Guardia: el script aborta si se ejecuta en {db_name} ({global_name}).")
        self.stdout.write(self.style.SUCCESS(f"Script escrito en {options['output']}"))
