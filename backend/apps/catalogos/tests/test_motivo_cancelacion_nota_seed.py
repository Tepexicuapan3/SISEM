"""Migracion 0041: catalogo MotivoCancelacionNota + seed idempotente (task 5.1)."""
import importlib

from django.apps import apps as django_apps
from django.test import TestCase

from apps.catalogos.models import MotivoCancelacionNota

SEED = ["Paciente equivocado", "Nota duplicada", "Error de captura", "Atención no realizada"]


class MotivoCancelacionNotaSeedTests(TestCase):
    def test_migracion_siembra_los_cuatro_motivos(self):
        names = set(MotivoCancelacionNota.objects.values_list("name", flat=True))
        self.assertTrue(set(SEED) <= names)
        self.assertEqual(MotivoCancelacionNota._meta.db_table, "cat_motivo_cancelacion_nota")

    def test_seed_es_idempotente_y_reactiva_bajas(self):
        migration = importlib.import_module("apps.catalogos.migrations.0041_motivo_cancelacion_nota")
        MotivoCancelacionNota.objects.filter(name="Nota duplicada").update(is_active=False)
        total = MotivoCancelacionNota.objects.count()

        migration.seed_motivos(django_apps, None)
        migration.seed_motivos(django_apps, None)

        self.assertEqual(MotivoCancelacionNota.objects.count(), total)
        self.assertTrue(MotivoCancelacionNota.objects.get(name="Nota duplicada").is_active)
