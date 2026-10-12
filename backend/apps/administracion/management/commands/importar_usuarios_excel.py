from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.administracion.services.user_import_service import ImportFileError
from apps.administracion.use_cases.users.import_users import (
    ConfirmUsersImportUseCase,
    PreviewUsersImportUseCase,
    RoleVanishedDuringImport,
)
from apps.authentication.models import SyUsuario


class Command(BaseCommand):
    help = (
        "Import masivo de usuarios desde el MISMO Excel de la pantalla "
        "'Importar usuarios' (misma plantilla, misma validacion, mismo alta). "
        "Pensado para cargas grandes que por HTTP exceden el timeout del proxy "
        "y bloquean al backend. Todo-o-nada: si una fila tiene error no se crea "
        "ningun usuario. --dry-run solo valida."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta al .xlsx dentro del contenedor.")
        parser.add_argument("--actor", required=True,
                            help="Usuario SIRES que queda registrado como quien dio de alta.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Solo valida el archivo y lista errores. No escribe nada.")

    def handle(self, *args, **options):
        actor = SyUsuario.objects.filter(usuario=options["actor"], est_activo=True).first()
        if actor is None:
            raise CommandError(f"El actor '{options['actor']}' no existe o esta inactivo.")

        try:
            with open(options["archivo"], "rb") as file:
                if options["dry_run"]:
                    result = PreviewUsersImportUseCase().execute(file)
                    has_errors = result["totalErrores"] > 0
                else:
                    self.stdout.write("Validando y creando usuarios (puede tardar varios minutos)...")
                    result = ConfirmUsersImportUseCase().execute(file, actor)
                    has_errors = result.pop("has_errors", False)
        except FileNotFoundError as exc:
            raise CommandError(f"No existe el archivo: {options['archivo']}") from exc
        except ImportFileError as exc:
            raise CommandError(f"{exc.code}: {exc.message} {exc.details or ''}") from exc
        except RoleVanishedDuringImport as exc:
            raise CommandError(f"{exc} No se creo ningun usuario.") from exc

        self.stdout.write(f"Filas: {result['totalRecords']}, con error: {result['totalErrores']}")

        if has_errors:
            for row in result["rows"]:
                if row["errors"]:
                    self.stdout.write(self.style.ERROR(f"  Fila {row['row']}: {'; '.join(row['errors'])}"))
            raise CommandError("El archivo tiene errores. No se creo ningun usuario.")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("[dry-run] Archivo valido. No se escribio nada."))
            return

        self.stdout.write(self.style.SUCCESS(f"Usuarios creados: {result['inserted']}"))
        failures = result["emailFailures"]
        if failures:
            self.stdout.write(self.style.WARNING(f"Correos que NO se enviaron: {len(failures)}"))
            for failure in failures:
                self.stdout.write(f"  {failure['username']}\t{failure['email']}")
