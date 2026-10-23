from django.core.management import call_command
from django.test import TestCase

from apps.administracion.management.seeds.navigation_seed import NAV_SEED
from apps.administracion.models import Modulo, ModuloPermiso
from apps.catalogos.models import Permisos


def _seed_permission_codes() -> set[str]:
    codigos: set[str] = set()
    for entry in NAV_SEED:
        codigos.update(entry["permisos"])
    return codigos


class SeedNavigationMenuCommandTests(TestCase):
    def _create_all_seed_permissions(self):
        for codigo in _seed_permission_codes():
            Permisos.objects.get_or_create(
                codigo=codigo,
                defaults={"descripcion": codigo, "es_sistema": False},
            )

    def test_seed_creates_every_node_from_nav_seed(self):
        self._create_all_seed_permissions()

        call_command("seed_navigation_menu")

        self.assertEqual(Modulo.objects.count(), len(NAV_SEED))
        for entry in NAV_SEED:
            modulo = Modulo.objects.get(clave=entry["clave"])
            self.assertEqual(modulo.titulo, entry["titulo"])
            self.assertEqual(modulo.es_seccion, entry["es_seccion"])
            self.assertEqual(modulo.grupo, entry["grupo"])
            if entry["parent_clave"]:
                self.assertEqual(modulo.id_parent.clave, entry["parent_clave"])
            else:
                self.assertIsNone(modulo.id_parent)

    def test_seed_is_idempotent_running_twice_does_not_duplicate_rows(self):
        self._create_all_seed_permissions()

        call_command("seed_navigation_menu")
        modulo_count_1 = Modulo.objects.count()
        permiso_count_1 = ModuloPermiso.objects.count()

        call_command("seed_navigation_menu")
        modulo_count_2 = Modulo.objects.count()
        permiso_count_2 = ModuloPermiso.objects.count()

        self.assertEqual(modulo_count_1, len(NAV_SEED))
        self.assertGreater(permiso_count_1, 0)
        self.assertEqual(modulo_count_1, modulo_count_2)
        self.assertEqual(permiso_count_1, permiso_count_2)

    def test_orphan_permission_code_logs_warning_and_does_not_abort(self):
        """
        Si un codigo de permiso referenciado en el seed NO existe en
        catalogos.Permisos, el comando debe loguearlo como warning, NO
        crear el permiso, y seguir sembrando el resto de los modulos sin
        abortar la corrida.
        """
        codigos = _seed_permission_codes()
        codigo_faltante = next(iter(codigos))
        # Las migraciones de datos ya pueden haber sembrado el codigo.
        Permisos.objects.filter(codigo=codigo_faltante).delete()
        for codigo in codigos:
            if codigo == codigo_faltante:
                continue
            Permisos.objects.get_or_create(
                codigo=codigo,
                defaults={"descripcion": codigo, "es_sistema": False},
            )

        call_command("seed_navigation_menu")

        # Todos los modulos se siembran igual, sin abortar la corrida.
        self.assertEqual(Modulo.objects.count(), len(NAV_SEED))

        # El codigo huerfano NUNCA se crea en catalogos.Permisos.
        self.assertFalse(Permisos.objects.filter(codigo=codigo_faltante).exists())

        # Ningun ModuloPermiso quedo apuntando a un permiso inexistente.
        modulos_afectados = [
            entry["clave"]
            for entry in NAV_SEED
            if codigo_faltante in entry["permisos"]
        ]
        for clave in modulos_afectados:
            modulo = Modulo.objects.get(clave=clave)
            self.assertFalse(
                ModuloPermiso.objects.filter(
                    id_modulo=modulo, id_permiso__codigo=codigo_faltante
                ).exists()
            )

    def test_dry_run_does_not_write_to_database(self):
        self._create_all_seed_permissions()

        call_command("seed_navigation_menu", "--dry-run")

        self.assertEqual(Modulo.objects.count(), 0)
        self.assertEqual(ModuloPermiso.objects.count(), 0)

    def test_prune_soft_deletes_modules_no_longer_in_seed(self):
        self._create_all_seed_permissions()
        call_command("seed_navigation_menu")

        stray = Modulo.objects.create(
            clave="obsoleto.no_esta_en_seed",
            titulo="Modulo obsoleto",
            orden=0,
            es_seccion=True,
            grupo=Modulo.Grupo.PRIMARY,
        )

        call_command("seed_navigation_menu", "--prune")

        stray.refresh_from_db()
        self.assertFalse(stray.is_active)
        self.assertIsNotNone(stray.fch_baja)
        # El resto de los modulos del seed siguen activos.
        self.assertEqual(
            Modulo.objects.filter(is_active=True).count(), len(NAV_SEED)
        )
