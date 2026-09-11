from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import ProtectedError
from django.db.utils import IntegrityError

from apps.authentication.models import SyUsuario
from apps.catalogos.models import Permisos, Roles
from apps.medicos.models import CatMedico
from apps.recepcion.models import Visit

# Usernames creados por seed_auth_access_base()/_demo()/_edge_cases()
# (domains/auth_access/infrastructure/bootstrap/auth_access_seeders.py).
AUTH_ACCESS_SEED_USERNAMES = (
    "admin",
    "user_base",
    "demo_support",
    "demo_auditor",
    "demo_manager",
    "edge_no_role",
    "edge_inactive_role_user",
)

# Usernames creados por seed_e2e.py (USER_DEFS).
E2E_SEED_USERNAMES = (
    "admin",
    "admin_usuarios",
    "admin_expedientes",
    "admin_roles",
    "admin_catalogos",
    "admin_reportes",
    "admin_estadisticas",
    "admin_autorizacion",
    "admin_licencias",
    "admin_conciliacion",
    "admin_lectura",
    "auditor_sistema",
    "clinico",
    "recepcion",
    "farmacia",
    "urgencias",
    "usuario_inactivo",
    "usuario_bloqueado",
    "usuario_onboarding",
    "usuario_cambiar_clave",
    "usuario_sin_centros",
    "usuario_onboarding_clinico",
    "usuario_onboarding_recepcion",
    "usuario_onboarding_farmacia",
    "usuario_onboarding_urgencias",
    "usuario_cambiar_clave_clinico",
    "usuario_cambiar_clave_admin",
    "usuario_inactivo_clinico",
    "usuario_inactivo_admin",
    "usuario_bloqueado_clinico",
    "usuario_bloqueado_admin",
    "usuario_multirol",
)

SEED_USERNAMES = sorted(set(AUTH_ACCESS_SEED_USERNAMES) | set(E2E_SEED_USERNAMES))

# Role codes de seed_e2e.py (ROLE_DEFS) + auth_access_seeders.py.
SEED_ROLE_CODES = (
    "admin",
    "user",
    "support",
    "auditor",
    "manager",
    "edge_role_without_permissions",
    "ADMIN",
    "ADMIN_USUARIOS",
    "ADMIN_EXPEDIENTES",
    "ADMIN_ROLES",
    "ADMIN_CATALOGOS",
    "ADMIN_REPORTES",
    "ADMIN_ESTADISTICAS",
    "ADMIN_AUTORIZACION",
    "ADMIN_LICENCIAS",
    "ADMIN_CONCILIACION",
    "ADMIN_SOLO_LECTURA",
    "SISTEMA_AUDITORIA",
    "ROL_INACTIVO_PRUEBA",
    "CLINICO",
    "RECEPCION",
    "FARMACIA",
    "URGENCIAS",
)

# Permission codes de seed_e2e.py (PERMISSIONS) + auth_access_seeders.py
# (BASE_PERMISSIONS + demo + edge-case).
SEED_PERMISSION_CODES = (
    "read_users",
    "write_users",
    "delete_users",
    "manage_roles",
    "read_audit",
    "read_profiles",
    "manage_password_resets",
    "edge_orphan_permission",
    "admin:gestion:usuarios:read",
    "admin:gestion:usuarios:create",
    "admin:gestion:usuarios:update",
    "admin:gestion:usuarios:delete",
    "admin:gestion:medicos:read",
    "admin:gestion:medicos:create",
    "admin:gestion:medicos:update",
    "admin:gestion:medicos:horarios",
    "admin:gestion:medicos:excepciones",
    "admin:gestion:medicos:coberturas",
    "admin:gestion:expedientes:read",
    "admin:gestion:roles:read",
    "admin:gestion:roles:create",
    "admin:gestion:roles:update",
    "admin:gestion:roles:delete",
    "admin:gestion:permisos:read",
    "admin:catalogos:centros_atencion:read",
    "admin:catalogos:centros_atencion:create",
    "admin:catalogos:centros_atencion:update",
    "admin:catalogos:centros_atencion:delete",
    "admin:catalogos:areas:read",
    "admin:catalogos:areas:create",
    "admin:catalogos:areas:update",
    "admin:catalogos:areas:delete",
    "admin:catalogos:vacunas:read",
    "admin:catalogos:vacunas:create",
    "admin:catalogos:vacunas:update",
    "admin:catalogos:vacunas:delete",
    "admin:catalogos:areas_clinicas:read",
    "admin:catalogos:areas_clinicas:create",
    "admin:catalogos:areas_clinicas:update",
    "admin:catalogos:areas_clinicas:delete",
    "admin:catalogos:centro_area_clinica:read",
    "admin:catalogos:centro_area_clinica:create",
    "admin:catalogos:centro_area_clinica:update",
    "admin:catalogos:centro_area_clinica:delete",
    "admin:catalogos:especialidades:read",
    "admin:catalogos:especialidades:create",
    "admin:catalogos:especialidades:update",
    "admin:catalogos:especialidades:delete",
    "admin:catalogos:tipo_consulta:read",
    "admin:catalogos:tipo_consulta:create",
    "admin:catalogos:tipo_consulta:update",
    "admin:catalogos:tipo_consulta:delete",
    "admin:reportes:read",
    "admin:estadisticas:read",
    "admin:autorizacion:recetas:read",
    "admin:autorizacion:estudios:read",
    "admin:licencias:read",
    "admin:conciliacion:read",
    "clinico:consultas:read",
    "clinico:consultas:agenda:read",
    "clinico:consultas:create",
    "clinico:consultas:historial:read",
    "clinico:expedientes:read",
    "clinico:expedientes:create",
    "clinico:somatometria:read",
    "recepcion:fichas:medicina_general:read",
    "recepcion:fichas:medicina_general:create",
    "recepcion:fichas:especialidad:read",
    "recepcion:fichas:especialidad:create",
    "recepcion:fichas:urgencias:read",
    "recepcion:fichas:urgencias:create",
    "recepcion:incapacidad:create",
    "recepcion:citas:read",
    "recepcion:citas:write",
    "farmacia:recetas:dispensar",
    "farmacia:inventario:update",
    "farmacia:vacunas:read",
    "farmacia:vacunas:create",
    "farmacia:vacunas:update",
    "farmacia:vacunas:delete",
    "urgencias:triage:read",
)

# Folios de visitas demo de seed_e2e.py (DEMO_VISITS).
SEED_VISIT_FOLIOS = (
    "RCP-DEMO-0001",
    "RCP-DEMO-0002",
    "SMT-DEMO-0001",
    "SMT-DEMO-0002",
    "SMT-DEMO-0003",
    "SMT-DEMO-0004",
    "DOC-DEMO-0001",
    "DOC-DEMO-0002",
    "DOC-DEMO-0003",
)

# --- Columnas que referencian sy_usuarios(id_usuario) a nivel de base de
# datos, clasificadas a mano tras introspeccionar produccion (2026-08-17).
#
# Motivo de esta clasificacion explicita: varios catalogos (CatalogBase)
# declaran usr_alta/usr_modf/usr_baja como BigIntegerField plano en vez de
# ForeignKey real. Django NO sabe que esas columnas son relaciones, asi que
# su logica de on_delete (CASCADE/SET_NULL/PROTECT) nunca corre para ellas
# -- pero la base de datos SI tiene la constraint FK real, y bloquea el
# DELETE en el COMMIT con un IntegrityError crudo. Confirmado en produccion
# para cat_centros_atencion/cat_permisos/cat_roles (incidente 2026-08-17).

# Estas SI son ForeignKey reales en Django (CASCADE o SET_NULL declarado) --
# se dejan como estan, el ORM ya las resuelve solo al borrar via .delete().
DJANGO_MANAGED_FK_COLUMNS = {
    ("auditoria_eventos", "actor_id_usuario"),
    ("auditoria_eventos", "target_id_usuario"),
    # cat_medicos.id_usuario pasó de on_delete=CASCADE a on_delete=SET_NULL
    # con el cambio medico-pk-independiente (Fase 4, F4-10) -- SIGUE siendo
    # una ForeignKey real de Django (el comentario de arriba ya cubre
    # "CASCADE o SET_NULL declarado"), el ORM la resuelve sola al borrar vía
    # `.delete()`. Lo que YA NO pasa es que el CatMedico se borre en
    # cascada: ahora sobrevive con id_usuario=NULL. Por eso, más abajo
    # (línea ~375), se agregó un `CatMedico.objects.filter(...).delete()`
    # EXPLÍCITO para seguir purgando médicos huérfanos del seed -- ver
    # Engram sdd/medico-pk-independiente/design, sección 9 (P2).
    ("cat_medicos", "id_usuario"),
    ("det_usuario_administrativo", "id_usuario"),
    ("det_usuario_cedulas", "id_usuario"),
    ("det_usuario_enfermeria", "id_usuario"),
    ("det_usuario_medico", "id_usuario"),
    ("det_usuarios", "id_usuario"),
    ("rcp_visits", "doctor_id"),
    ("rel_rol_permisos", "usr_asignacion"),
    ("rel_rol_permisos", "usr_baja"),
    ("rel_usuario_overrides", "id_usuario"),
    ("rel_usuario_overrides", "usr_asignacion"),
    ("rel_usuario_overrides", "usr_baja"),
    ("rel_usuario_roles", "id_usuario"),
    ("rel_usuario_roles", "usr_asignacion"),
    ("rel_usuario_roles", "usr_baja"),
    ("sy_sesiones_usuario", "id_usuario"),
    ("sy_usuarios", "usr_alta"),
    ("sy_usuarios", "usr_baja"),
    ("sy_usuarios", "usr_modf"),
}

# Estas tienen on_delete=PROTECT real en Django -- NUNCA se auto-nulean.
# Si bloquean el borrado es a proposito (datos clinicos/legales reales).
PROTECTED_FK_COLUMNS = {
    ("cat_autorizadores", "id_usuario"),
    ("cns_visit_consultation", "id_doctor"),
}

# Estas NO son ForeignKey en Django (BigIntegerField plano via CatalogBase)
# pero SI tienen constraint FK real en Postgres -- hay que ponerlas en NULL
# a mano antes de borrar el usuario, o el DELETE falla en el COMMIT.
UNTRACKED_NULLABLE_FK_COLUMNS = {
    ("cat_centros_atencion", "usr_alta"),
    ("cat_centros_atencion", "usr_baja"),
    ("cat_centros_atencion", "usr_modf"),
    ("cat_permisos", "usr_alta"),
    ("cat_permisos", "usr_baja"),
    ("cat_permisos", "usr_modf"),
    ("cat_roles", "usr_alta"),
    ("cat_roles", "usr_baja"),
    ("cat_roles", "usr_modf"),
}


def _discover_user_fk_columns(cursor):
    cursor.execute(
        """
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'sy_usuarios'
          AND ccu.column_name = 'id_usuario'
        """
    )
    return {(table, column) for table, column in cursor.fetchall()}


class Command(BaseCommand):
    help = (
        "Borra SOLO los usuarios/roles/permisos/visitas creados por los "
        "seeders conocidos (seed_auth_access --base/--demo/--edge-cases y "
        "seed_e2e.py), identificados por username/codigo/folio exactos. "
        "No toca ningun otro registro. Por defecto corre en modo vista "
        "previa (no borra nada) -- pasa --confirm para ejecutar de verdad."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Ejecuta el borrado de verdad. Sin esto, solo muestra que se borraria.",
        )
        parser.add_argument(
            "--keep-username",
            action="append",
            default=[],
            help=(
                "Username a excluir del borrado aunque este en la lista de seed "
                "(por ejemplo, si ya creaste tu admin real con el mismo nombre "
                "'admin' que usa el seed). Se puede repetir."
            ),
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]
        keep_usernames = set(options["keep_username"])

        usernames_to_delete = [
            u for u in SEED_USERNAMES if u not in keep_usernames
        ]

        users_qs = SyUsuario.objects.filter(usuario__in=usernames_to_delete)
        roles_qs = Roles.objects.filter(rol__in=SEED_ROLE_CODES)
        permissions_qs = Permisos.objects.filter(codigo__in=SEED_PERMISSION_CODES)
        visits_qs = Visit.objects.filter(folio__in=SEED_VISIT_FOLIOS)

        found_usernames = sorted(users_qs.values_list("usuario", flat=True))
        found_user_ids = list(users_qs.values_list("id_usuario", flat=True))
        found_roles = sorted(roles_qs.values_list("rol", flat=True))
        found_permissions = sorted(permissions_qs.values_list("codigo", flat=True))
        found_visits = sorted(visits_qs.values_list("folio", flat=True))

        skipped_usernames = sorted(
            u for u in SEED_USERNAMES if u in keep_usernames
        )

        self.stdout.write("=== Vista previa ===")
        self.stdout.write(f"Usuarios a borrar ({len(found_usernames)}): {found_usernames}")
        if skipped_usernames:
            self.stdout.write(
                f"Usuarios EXCLUIDOS por --keep-username ({len(skipped_usernames)}): {skipped_usernames}"
            )
        self.stdout.write(f"Roles a borrar ({len(found_roles)}): {found_roles}")
        self.stdout.write(f"Permisos a borrar ({len(found_permissions)}): {found_permissions}")
        self.stdout.write(f"Visitas demo a borrar ({len(found_visits)}): {found_visits}")

        with connection.cursor() as cursor:
            all_fk_columns = _discover_user_fk_columns(cursor)

        known_columns = (
            DJANGO_MANAGED_FK_COLUMNS | PROTECTED_FK_COLUMNS | UNTRACKED_NULLABLE_FK_COLUMNS
        )
        unrecognized_columns = sorted(all_fk_columns - known_columns)
        if unrecognized_columns:
            self.stderr.write(
                self.style.ERROR(
                    "Borrado abortado (no se toco nada): se encontraron columnas que "
                    "referencian sy_usuarios y que este comando no reconoce -- puede "
                    "ser una tabla nueva con el mismo problema de "
                    "CatalogBase/BigIntegerField sin ForeignKey real. Clasificala en "
                    "clean_seed_data.py (DJANGO_MANAGED / PROTECTED / "
                    "UNTRACKED_NULLABLE) antes de reintentar:"
                )
            )
            for table, column in unrecognized_columns:
                self.stderr.write(f"  - {table}.{column}")
            return

        untracked_to_null = sorted(all_fk_columns & UNTRACKED_NULLABLE_FK_COLUMNS)

        if not confirm:
            if untracked_to_null and found_user_ids:
                self.stdout.write(
                    f"Columnas sin FK de Django que se pondran en NULL antes de "
                    f"borrar ({len(untracked_to_null)}): {untracked_to_null}"
                )
            self.stdout.write(
                self.style.WARNING(
                    "\nModo vista previa -- no se borro nada. Corre con --confirm para ejecutar."
                )
            )
            return

        try:
            with transaction.atomic():
                if found_user_ids:
                    with connection.cursor() as cursor:
                        for table, column in untracked_to_null:
                            cursor.execute(
                                f'UPDATE "{table}" SET "{column}" = NULL '
                                f'WHERE "{column}" = ANY(%s)',
                                [found_user_ids],
                            )

                visits_qs.delete()
                # F4-11 (medico-pk-independiente): id_usuario ya no cascadea
                # (CASCADE -> SET_NULL, ver DJANGO_MANAGED_FK_COLUMNS arriba)
                # -- un CatMedico seed sobreviviría con id_usuario=NULL si no
                # se borra explícitamente ANTES de borrar los usuarios.
                CatMedico.objects.filter(id_usuario_id__in=found_user_ids).delete()
                users_qs.delete()
                roles_qs.delete()
                permissions_qs.delete()
        except ProtectedError as exc:
            protected_objects = list(exc.args[1]) if len(exc.args) > 1 else []
            self.stderr.write(
                self.style.ERROR(
                    "Borrado abortado (nada se toco, la transaccion se revirtio): "
                    f"{len(protected_objects)} registro(s) real(es) dependen de un "
                    "usuario/rol de la lista de seed (ej. consultas medicas ya "
                    "firmadas). Revisa esos registros antes de borrar ese usuario "
                    "puntual, o excluilo con --keep-username."
                )
            )
            for obj in protected_objects[:20]:
                self.stderr.write(f"  - {obj!r}")
            return
        except IntegrityError as exc:
            self.stderr.write(
                self.style.ERROR(
                    "Borrado abortado (nada se toco, la transaccion se revirtio): "
                    "violacion de integridad no anticipada. Puede ser una constraint "
                    "nueva no clasificada en este comando. Detalle:\n"
                    f"{exc}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\nBorrado OK: {len(found_usernames)} usuario(s), {len(found_roles)} rol(es), "
                f"{len(found_permissions)} permiso(s), {len(found_visits)} visita(s) demo "
                "(mas sus filas relacionadas en cascada: perfiles, asignaciones de rol, etc.)."
            )
        )
