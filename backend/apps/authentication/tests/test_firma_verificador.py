"""VerificadorSimple + regla REAUTH_FAIL_LOCK (S20, S21). Sin base de datos."""
import hashlib
from types import SimpleNamespace

from django.contrib.auth.hashers import make_password
from django.test import SimpleTestCase

from apps.authentication.application.auth_policy_service import AuthPolicyService
from apps.authentication.domain.auth_policy_rules import REAUTH_FAIL_LOCK
from apps.authentication.services.errors import AuthServiceError, PolicyStoreUnavailableError
from apps.authentication.services.firma import (
    ResultadoFirma,
    VerificadorFirma,
    VerificadorSimple,
)


class FakePolicyStore:
    """Misma interfaz que PolicyStore, en memoria y sin TTL."""

    def __init__(self):
        self.counters = {}
        self.locks = set()
        self.unavailable = False

    def _check(self):
        if self.unavailable:
            raise PolicyStoreUnavailableError("down")

    def increment_counter(self, key, ttl_seconds):
        self._check()
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def get_counter(self, key):
        self._check()
        return self.counters.get(key, 0)

    def clear_counter(self, key):
        self._check()
        self.counters.pop(key, None)
        self.locks.discard(key)

    def set_lock(self, key, ttl_seconds):
        self._check()
        self.locks.add(key)

    def is_locked(self, key):
        self._check()
        return key in self.locks


PASSWORD = "Clave_Correcta_1"


class VerificadorSimpleTests(SimpleTestCase):
    def setUp(self):
        self.store = FakePolicyStore()
        self.verificador = VerificadorSimple(policy_service=AuthPolicyService(self.store))
        self.user = SimpleNamespace(id_usuario=42, clave_hash=make_password(PASSWORD))

    def _fail(self):
        with self.assertRaises(AuthServiceError) as ctx:
            self.verificador.verificar(self.user, "incorrecta", b"contenido")
        return ctx.exception

    def test_cumple_el_protocolo_verificador_firma(self):
        self.assertIsInstance(self.verificador, VerificadorFirma)

    def test_password_correcta_devuelve_resultado_con_hash_sha256(self):
        contenido = '{"a":1}'
        result = self.verificador.verificar(self.user, PASSWORD, contenido)
        self.assertIsInstance(result, ResultadoFirma)
        self.assertEqual(result.metodo, "SIMPLE")
        self.assertEqual(result.hash_contenido, hashlib.sha256(contenido.encode()).hexdigest())
        self.assertEqual(len(result.hash_contenido), 64)
        self.assertIsNotNone(result.firmado_en)

    def test_mismo_contenido_mismo_hash_y_bytes_equivale_a_str(self):
        a = self.verificador.verificar(self.user, PASSWORD, "x")
        b = self.verificador.verificar(self.user, PASSWORD, b"x")
        self.assertEqual(a.hash_contenido, b.hash_contenido)

    def test_s20_password_incorrecta_es_403_reauth_failed_nunca_401(self):
        error = self._fail()
        self.assertEqual(error.code, "REAUTH_FAILED")
        self.assertEqual(error.status_code, 403)
        self.assertEqual(self.store.counters["policy:reauth:firma:counter:42"], 1)

    def test_password_vacia_o_ausente_cuenta_como_fallo(self):
        for credencial in (None, ""):
            with self.assertRaises(AuthServiceError) as ctx:
                self.verificador.verificar(self.user, credencial, b"x")
            self.assertEqual(ctx.exception.code, "REAUTH_FAILED")
        self.assertEqual(self.store.counters["policy:reauth:firma:counter:42"], 2)

    def test_s21_tras_umbral_fallos_bloquea_aun_con_password_correcta(self):
        self.assertEqual(REAUTH_FAIL_LOCK.threshold, 5)
        for _ in range(REAUTH_FAIL_LOCK.threshold):
            self.assertEqual(self._fail().code, "REAUTH_FAILED")

        with self.assertRaises(AuthServiceError) as ctx:
            self.verificador.verificar(self.user, PASSWORD, b"x")
        self.assertEqual(ctx.exception.code, "REAUTH_LOCKED")
        self.assertEqual(ctx.exception.status_code, 423)
        policy = ctx.exception.details["policy"]
        self.assertEqual(policy["policyKey"], "reauth.firma.lock")
        self.assertEqual(policy["lockTtl"], 15 * 60)

    def test_bloqueo_no_cuenta_mas_intentos(self):
        for _ in range(REAUTH_FAIL_LOCK.threshold):
            self._fail()
        with self.assertRaises(AuthServiceError):
            self.verificador.verificar(self.user, "otra", b"x")
        self.assertEqual(self.store.counters["policy:reauth:firma:counter:42"], 5)

    def test_exito_antes_del_umbral_reinicia_el_contador(self):
        for _ in range(REAUTH_FAIL_LOCK.threshold - 1):
            self._fail()
        self.verificador.verificar(self.user, PASSWORD, b"x")
        self.assertNotIn("policy:reauth:firma:counter:42", self.store.counters)
        for _ in range(REAUTH_FAIL_LOCK.threshold - 1):
            self.assertEqual(self._fail().code, "REAUTH_FAILED")  # sigue sin bloquear

    def test_el_bloqueo_es_por_usuario(self):
        for _ in range(REAUTH_FAIL_LOCK.threshold):
            self._fail()
        otro = SimpleNamespace(id_usuario=43, clave_hash=make_password(PASSWORD))
        self.assertEqual(self.verificador.verificar(otro, PASSWORD, b"x").metodo, "SIMPLE")

    def test_policy_store_caido_falla_cerrado_con_503(self):
        self.store.unavailable = True
        with self.assertRaises(AuthServiceError) as ctx:
            self.verificador.verificar(self.user, PASSWORD, b"x")
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.code, "SERVICE_UNAVAILABLE")
