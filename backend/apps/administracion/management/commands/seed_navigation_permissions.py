from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.administracion.management.seeds.navigation_permissions_seed import (
    NAVIGATION_PERMISSIONS_SEED,
)
from apps.administracion.models import RelRolPermiso
from apps.catalogos.models import Permisos, Roles

logger = logging.getLogger(__name__)

CATALOGOS_PREFIX = "admin:catalogos:"


class Command(BaseCommand):
    help = (
        "Da de alta (idempotente) los permisos de cat_permisos que "
        "navigation_seed.py referencia y que la auditoria del change "
        "menu-modulos clasifico como categoria A (feature real, solo "
        "faltaba el codigo en cat_permisos). Correrlo ANTES de "
        "seed_navigation_menu para que esos codigos dejen de reportarse "
        "como huerfanos. Los codigos admin:catalogos:* se asignan ademas "
        "a los roles con is_admin=True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No escribe en la base de datos, solo reporta que haria.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        with transaction.atomic():
            summary = self._run()
            if dry_run:
                transaction.set_rollback(True)

        self._report(summary, dry_run=dry_run)

    # ------------------------------------------------------------------
    def _run(self) -> dict:
        created = 0
        updated = 0
        asignaciones_creadas = 0

        admin_roles = list(Roles.objects.filter(is_admin=True, is_active=True))

        for codigo, descripcion in NAVIGATION_PERMISSIONS_SEED:
            permiso, fue_creado = Permisos.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "descripcion": descripcion,
                    "is_active": True,
                    "es_sistema": False,
                    "updated_at": timezone.now(),
                },
            )

            # Los catalogos administrativos se asignan a los roles admin, igual
            # que hace seed_catalogos_crud_permissions con los catalogos CRUD.
            if codigo.startswith(CATALOGOS_PREFIX):
                for rol in admin_roles:
                    _, fue_asignado = RelRolPermiso.objects.get_or_create(
                        id_rol=rol,
                        id_permiso=permiso,
                        defaults={"fch_baja": None},
                    )
                    if fue_asignado:
                        asignaciones_creadas += 1

            if fue_creado:
                created += 1
                continue

            cambio = False
            if permiso.descripcion != descripcion:
                permiso.descripcion = descripcion
                cambio = True
            if not permiso.is_active:
                permiso.is_active = True
                cambio = True
            if cambio:
                permiso.updated_at = timezone.now()
                permiso.save(update_fields=["descripcion", "is_active", "updated_at"])
                updated += 1

        return {
            "total": len(NAVIGATION_PERMISSIONS_SEED),
            "created": created,
            "updated": updated,
            "asignaciones_creadas": asignaciones_creadas,
            "roles_admin": [rol.rol for rol in admin_roles],
        }

    # ------------------------------------------------------------------
    def _report(self, summary: dict, *, dry_run: bool) -> None:
        prefijo = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefijo}[seed_navigation_permissions] total={summary['total']} "
                f"creados={summary['created']} actualizados={summary['updated']} "
                f"asignaciones_creadas={summary['asignaciones_creadas']} "
                f"roles_admin={summary['roles_admin']}"
            )
        )
