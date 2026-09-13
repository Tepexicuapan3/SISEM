from __future__ import annotations

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.crypto import get_random_string

from apps.authentication.management.commands._legacy_mysql_base import LegacyMysqlCommandMixin
from apps.authentication.models import SyUsuario

PLACEHOLDER_DOMAIN = "pendiente.sires.local"


class Command(LegacyMysqlCommandMixin, BaseCommand):
    help = (
        "Migra usuarios desde cat_usuarios (MySQL, sistema anterior) a sy_usuarios. "
        "Genera correo placeholder y clave aleatoria; deja la cuenta bloqueada "
        "hasta que un admin cargue el correo real y el usuario resetee su clave."
    )

    def add_arguments(self, parser):
        self.add_legacy_mysql_arguments(parser)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No escribe nada, solo muestra qué se migraría.",
        )

    def handle(self, *args, **options):
        conn = self.conectar_legado(options)

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT cd_usuario, nm_usuario FROM cat_usuarios"
                )
                rows = cursor.fetchall()
        finally:
            conn.close()

        existentes = set(
            SyUsuario.objects.filter(
                usuario__in=[row["cd_usuario"].strip() for row in rows]
            ).values_list("usuario", flat=True)
        )

        creados, omitidos = 0, 0
        nuevos = []

        for row in rows:
            usuario = row["cd_usuario"].strip()
            if usuario in existentes:
                omitidos += 1
                continue

            nuevos.append(
                SyUsuario(
                    usuario=usuario,
                    correo=f"{usuario.lower()}@{PLACEHOLDER_DOMAIN}",
                    clave_hash=make_password(get_random_string(32)),
                    cambiar_clave=True,
                    est_activo=True,
                    est_bloqueado=True,
                )
            )
            creados += 1

        if options["dry_run"]:
            self.stdout.write(
                self.style.NOTICE(
                    f"[dry-run] Se migrarían {creados} usuarios, {omitidos} ya existían."
                )
            )
            return

        with transaction.atomic():
            SyUsuario.objects.bulk_create(nuevos, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"Migración completa: {creados} usuarios creados, {omitidos} omitidos (ya existían)."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Quedaron con est_bloqueado=True y correo placeholder. "
                "Actualizá correo real y desbloqueá desde el admin antes de habilitar login."
            )
        )
