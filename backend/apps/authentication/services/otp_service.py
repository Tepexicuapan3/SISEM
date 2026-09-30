import secrets

from django.core.cache import cache

from apps.authentication.domain.auth_policy_rules import OTP_RULE
from apps.authentication.infrastructure.policy_store import PolicyStore

# Limites de solicitudes e intentos: los aplica AuthPolicyService
# (check_reset_request / record_verify_failure), no este modulo.
OTP_TTL_SECONDS = OTP_RULE.otp_ttl_seconds or 300

policy_store = PolicyStore()


def generate_code():
    # Genera codigo de 6 digitos.
    return str(secrets.randbelow(10**6)).zfill(6)


def store_code(email, code):
    # Guarda codigo en cache con TTL.
    policy_store.set_otp(email, code, OTP_TTL_SECONDS)
    cache.set(_otp_attempts_key(email), 0, OTP_TTL_SECONDS)


def get_code(email):
    # Obtiene codigo desde cache.
    code = policy_store.get_otp(email)
    if not code:
        return None
    return {"code": code, "attempts": cache.get(_otp_attempts_key(email), 0)}


def consume_code_atomic(email, code):
    return policy_store.consume_otp(email, code)


def _otp_attempts_key(email):
    return f"otp:attempts:{email.lower()}"
