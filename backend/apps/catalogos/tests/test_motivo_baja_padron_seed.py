"""Migracion 0044: catalogo MotivoBajaPadron + seed idempotente (padrones-clinicos, P-04)."""
import importlib

from django.apps import apps as django_apps
from django.test import TestCase

from apps.catalogos.models import MotivoBajaPadron

SEED = [
    "Diagnóstico descartado",
    "Alta del programa por control",
    "Registro erróneo",
    "Defunción",
    "Pérdida de derechohabiencia",
    "Cambio de unidad",
]


class MotivoBajaPadronSeedTests(TestCase):
    def test_migracion_siembra_los_seis_motivos(self):
        names = set(MotivoBajaPadron.objects.values_list("name", flat=True))
        self.assertTrue(set(SEED) <= names)
        self.assertEqual(MotivoBajaPadron._meta.db_table, "cat_motivo_baja_padron")

    def test_seed_es_idempotente_y_reactiva_bajas(self):
        migration = importlib.import_module("apps.catalogos.migrations.0044_motivo_baja_padron")
        MotivoBajaPadron.objects.filter(name="Defunción").update(is_active=False)
        total = MotivoBajaPadron.objects.count()

        migration.seed_motivos(django_apps, None)
        migration.seed_motivos(django_apps, None)

        self.assertEqual(MotivoBajaPadron.objects.count(), total)
        self.assertTrue(MotivoBajaPadron.objects.get(name="Defunción").is_active)
