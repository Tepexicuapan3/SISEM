from unittest import mock

from django.core.cache import cache
from django.db import transaction
from django.test import RequestFactory, TestCase

from apps.administracion.models import BitacoraAcceso
from apps.authentication.models import SyUsuario
from apps.consulta_medica.services.record_access_audit_service import RecordSection, log_print


class LogPrintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = SyUsuario.objects.create(usuario="u_log_print", clave_hash="x")

    def _request(self):
        return RequestFactory().get("/api/v1/impresion/ficha/9")

    def test_sections_registered(self):
        for s in (RecordSection.FICHA, RecordSection.RECETA, RecordSection.NOTA):
            self.assertIn(s, RecordSection.ALL)
        self.assertEqual(
            (RecordSection.FICHA, RecordSection.RECETA, RecordSection.NOTA),
            ("ficha_consulta", "receta", "nota_clinica"),
        )

    def test_writes_imprimir_row(self):
        log_print(self._request(), self.user, no_exp="E1", pk_num=2, section=RecordSection.FICHA)
        row = BitacoraAcceso.objects.get()
        self.assertEqual(row.accion, BitacoraAcceso.Accion.IMPRIMIR)
        self.assertEqual((row.no_exp, row.tp_paciente), ("E1", 2))
        self.assertEqual(row.recurso, "ficha_consulta")
        self.assertEqual(row.cd_usuario, "u_log_print")
        self.assertEqual(row.endpoint, "/api/v1/impresion/ficha/9")

    def test_no_dedup(self):
        cache.clear()
        for _ in range(3):
            log_print(self._request(), self.user, no_exp="E1", pk_num=0, section=RecordSection.NOTA)
        self.assertEqual(BitacoraAcceso.objects.count(), 3)

    def test_raises_on_failure_and_rolls_back_in_atomic(self):
        with mock.patch.object(
            BitacoraAcceso.objects, "create", side_effect=RuntimeError("db down")
        ):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    log_print(self._request(), self.user, no_exp="E1", pk_num=0, section=RecordSection.RECETA)
        self.assertEqual(BitacoraAcceso.objects.count(), 0)
