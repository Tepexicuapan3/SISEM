from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyRule:
    key: str
    threshold: int
    window_seconds: int
    window_label: str
    lock_ttl_seconds: int | None = None
    otp_ttl_seconds: int | None = None


LOGIN_ACCOUNT_LOCK = PolicyRule(
    key="login.account.lock",
    threshold=5,
    window_seconds=15 * 60,
    window_label="15m",
    lock_ttl_seconds=15 * 60,
)

LOGIN_IP_THROTTLE = PolicyRule(
    key="login.ip.throttle",
    threshold=20,
    window_seconds=5 * 60,
    window_label="5m",
)

RESET_REQUEST_ACCOUNT = PolicyRule(
    key="reset.request.account",
    threshold=3,
    window_seconds=15 * 60,
    window_label="15m",
)

RESET_REQUEST_IP = PolicyRule(
    key="reset.request.ip",
    threshold=10,
    window_seconds=15 * 60,
    window_label="15m",
)

VERIFY_FAIL_LOCK = PolicyRule(
    key="reset.verify.lock",
    threshold=5,
    window_seconds=10 * 60,
    window_label="10m",
    lock_ttl_seconds=15 * 60,
)

OTP_RULE = PolicyRule(
    key="otp.ttl",
    threshold=1,
    window_seconds=5 * 60,
    window_label="5m",
    otp_ttl_seconds=5 * 60,
)

# Re-autenticacion con contrasena propia para acciones firmadas (ej. cancelar
# nota; change cancelacion-nota-cascada). Clave por id_usuario: 5 fallos en
# 15 min bloquean 15 min, aun con la contrasena correcta.
REAUTH_FAIL_LOCK = PolicyRule(
    key="reauth.firma.lock",
    threshold=5,
    window_seconds=15 * 60,
    window_label="15m",
    lock_ttl_seconds=15 * 60,
)
