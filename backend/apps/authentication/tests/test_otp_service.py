from apps.authentication.services.otp_service import generate_code, get_code, store_code
from django.test import TestCase, override_settings


# Los limites de solicitudes/intentos del OTP los aplica AuthPolicyService y
# se prueban en sus propios tests; aca solo el guardado/lectura del codigo.
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class OtpServiceTests(TestCase):
    def test_store_and_get_code(self):
        email = "user@example.com"
        code = generate_code()
        store_code(email, code)

        data = get_code(email)

        self.assertIsNotNone(data)
        data = data or {}
        self.assertEqual(data["code"], code)
