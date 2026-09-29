"""
Administra CAT_PERFIL_ACCESO (documento "Historia Clinica Unificada"):
que roles ven SIN redaccion los diagnosticos sensibles de una categoria
(VIH, salud mental, sustancias). La decision de que perfiles se habilitan es
del area medica con la de datos personales (documento, decisiones
pendientes) -- este comando solo la aplica.

Ejemplos:
    python manage.py perfil_acceso_sensible --listar
    python manage.py perfil_acceso_sensible --agregar --categoria hiv --rol INFECTOLOGIA
    python manage.py perfil_acceso_sensible --quitar --categoria hiv --rol INFECTOLOGIA
"""
from django.core.management.base import BaseCommand, CommandError

from apps.catalogos.models import Roles, SensitiveAccessProfile, SensitiveCieRange
from apps.catalogos.services.sensitive_diagnosis_service import invalidate_cache


class Command(BaseCommand):
    help = "Lista, agrega o quita perfiles (roles) con acceso a diagnosticos sensibles."

    def add_arguments(self, parser):
        action = parser.add_mutually_exclusive_group(required=True)
        action.add_argument("--listar", action="store_true")
        action.add_argument("--agregar", action="store_true")
        action.add_argument("--quitar", action="store_true")
        parser.add_argument("--categoria", help=f"Una de: {', '.join(SensitiveCieRange.Category.values)}")
        parser.add_argument("--rol", help="Codigo del rol (cat_roles.rol)")

    def handle(self, *args, **options):
        if options["listar"]:
            for profile in SensitiveAccessProfile.objects.select_related("sensitive_range", "role").order_by(
                "sensitive_range__code_prefix_start", "role__rol",
            ):
                self.stdout.write(f"{profile.sensitive_range} -> {profile.role.rol}")
            return

        category, role_code = options.get("categoria"), (options.get("rol") or "").strip().upper()
        if not category or not role_code:
            raise CommandError("--categoria y --rol son obligatorios para --agregar/--quitar.")
        ranges = list(SensitiveCieRange.objects.filter(category=category, is_active=True))
        if not ranges:
            raise CommandError(f"No hay rangos activos para la categoria '{category}'.")
        role = Roles.objects.filter(rol__iexact=role_code).first()
        if role is None:
            raise CommandError(f"No existe el rol '{role_code}'.")

        for sensitive_range in ranges:
            if options["agregar"]:
                SensitiveAccessProfile.objects.get_or_create(sensitive_range=sensitive_range, role=role)
            else:
                SensitiveAccessProfile.objects.filter(sensitive_range=sensitive_range, role=role).delete()
        invalidate_cache()
        verb = "habilitado" if options["agregar"] else "retirado"
        self.stdout.write(self.style.SUCCESS(
            f"Rol {role.rol} {verb} para {len(ranges)} rango(s) de la categoria {category}. "
            "Reiniciar los workers del backend para que tomen el cambio (cache en proceso)."
        ))
