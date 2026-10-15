from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.authentication.models import SyUsuario
from apps.impresion.models import PrintCounter, PrintLog
from apps.impresion.repositories.print_log_repository import PrintLogRepository


def _log_fields(user, copy_number, **overrides):
    data = dict(
        documento="ficha",
        resource_id=10,
        folio="F-1",
        copy_number=copy_number,
        tipo="ORIGINAL" if copy_number == 1 else "REIMPRESION",
        user=user,
        user_code=user.usuario,
        sha256="a" * 64,
    )
    data.update(overrides)
    return data


class PrintLogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = SyUsuario.objects.create(usuario="u_print", clave_hash="x")

    def test_unique_constraint_documento_recurso_copia(self):
        PrintLog.objects.create(**_log_fields(self.user, 1))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrintLog.objects.create(**_log_fields(self.user, 1))
        # otra copia / otro recurso / otro documento si se permiten
        PrintLog.objects.create(**_log_fields(self.user, 2))
        PrintLog.objects.create(**_log_fields(self.user, 1, resource_id=11))
        PrintLog.objects.create(**_log_fields(self.user, 1, documento="nota"))
        self.assertEqual(PrintLog.objects.count(), 4)

    def test_counter_unique_per_documento_recurso(self):
        PrintCounter.objects.create(documento="ficha", resource_id=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrintCounter.objects.create(documento="ficha", resource_id=1)

    def test_no_json_fields(self):
        for model in (PrintLog, PrintCounter):
            for field in model._meta.get_fields():
                self.assertNotEqual(field.get_internal_type(), "JSONField")


class PrintLogRepositoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = SyUsuario.objects.create(usuario="u_repo", clave_hash="x")

    def test_reserve_copy_increments_per_resource(self):
        with transaction.atomic():
            self.assertEqual(PrintLogRepository.reserve_copy("ficha", 5), 1)
            self.assertEqual(PrintLogRepository.reserve_copy("ficha", 5), 2)
            self.assertEqual(PrintLogRepository.reserve_copy("ficha", 6), 1)
            self.assertEqual(PrintLogRepository.reserve_copy("nota", 5), 1)

    def test_reserve_copy_rolls_back_with_transaction(self):
        try:
            with transaction.atomic():
                PrintLogRepository.reserve_copy("ficha", 7)
                raise RuntimeError("render fail")
        except RuntimeError:
            pass
        with transaction.atomic():
            self.assertEqual(PrintLogRepository.reserve_copy("ficha", 7), 1)

    def test_create_log_duplicate_raises_integrity_error(self):
        with transaction.atomic():
            n = PrintLogRepository.reserve_copy("ficha", 8)
            PrintLogRepository.create_log(**_log_fields(self.user, n, resource_id=8))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrintLogRepository.create_log(**_log_fields(self.user, n, resource_id=8))
