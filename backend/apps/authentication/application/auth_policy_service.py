from apps.authentication.domain.auth_policy_rules import (
    LOGIN_ACCOUNT_LOCK,
    LOGIN_IP_THROTTLE,
    REAUTH_FAIL_LOCK,
    RESET_REQUEST_ACCOUNT,
    RESET_REQUEST_IP,
    VERIFY_FAIL_LOCK,
)
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.services.errors import (
    AuthServiceError,
    PolicyStoreUnavailableError,
)


class AuthPolicyService:
    def __init__(self, policy_store=None):
        self.policy_store = policy_store or PolicyStore()

    def check_login(self, username: str, ip_address: str | None):
        username_key = username.lower()
        ip_key = self._ip_key(ip_address)

        try:
            if self.policy_store.is_locked(self._login_account_lock_key(username_key)):
                counter_value = self.policy_store.get_counter(
                    self._login_account_counter_key(username_key)
                )
                raise self._policy_error(
                    "ACCOUNT_LOCKED",
                    "Cuenta bloqueada por intentos fallidos",
                    423,
                    {
                        "policyKey": LOGIN_ACCOUNT_LOCK.key,
                        "threshold": LOGIN_ACCOUNT_LOCK.threshold,
                        "window": LOGIN_ACCOUNT_LOCK.window_label,
                        "counterValue": counter_value,
                        "lockTtl": LOGIN_ACCOUNT_LOCK.lock_ttl_seconds,
                    },
                )

            ip_counter = self.policy_store.get_counter(
                self._login_ip_counter_key(ip_key)
            )
            if ip_counter >= LOGIN_IP_THROTTLE.threshold:
                raise self._policy_error(
                    "RATE_LIMIT_EXCEEDED",
                    "Demasiadas solicitudes, espera un momento",
                    429,
                    {
                        "policyKey": LOGIN_IP_THROTTLE.key,
                        "threshold": LOGIN_IP_THROTTLE.threshold,
                        "window": LOGIN_IP_THROTTLE.window_label,
                        "counterValue": ip_counter,
                        "lockTtl": LOGIN_IP_THROTTLE.window_seconds,
                    },
                )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def record_login_failure(self, username: str, ip_address: str | None):
        username_key = username.lower()
        ip_key = self._ip_key(ip_address)

        try:
            account_counter = self.policy_store.increment_counter(
                self._login_account_counter_key(username_key),
                LOGIN_ACCOUNT_LOCK.window_seconds,
            )
            self.policy_store.increment_counter(
                self._login_ip_counter_key(ip_key),
                LOGIN_IP_THROTTLE.window_seconds,
            )

            if account_counter >= LOGIN_ACCOUNT_LOCK.threshold:
                self.policy_store.set_lock(
                    self._login_account_lock_key(username_key),
                    LOGIN_ACCOUNT_LOCK.lock_ttl_seconds
                    or LOGIN_ACCOUNT_LOCK.window_seconds,
                )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def record_login_success(self, username: str, ip_address: str | None):
        username_key = username.lower()
        ip_key = self._ip_key(ip_address)

        try:
            self.policy_store.clear_counter(
                self._login_account_counter_key(username_key)
            )
            self.policy_store.clear_counter(self._login_ip_counter_key(ip_key))
            self.policy_store.clear_counter(self._login_account_lock_key(username_key))
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def check_reset_request(self, email: str, ip_address: str | None):
        email_key = email.lower()
        ip_key = self._ip_key(ip_address)

        try:
            account_counter = self.policy_store.get_counter(
                self._reset_request_account_key(email_key)
            )
            if account_counter >= RESET_REQUEST_ACCOUNT.threshold:
                raise self._policy_error(
                    "RATE_LIMIT_EXCEEDED",
                    "Demasiadas solicitudes, espera un momento",
                    429,
                    {
                        "policyKey": RESET_REQUEST_ACCOUNT.key,
                        "threshold": RESET_REQUEST_ACCOUNT.threshold,
                        "window": RESET_REQUEST_ACCOUNT.window_label,
                        "counterValue": account_counter,
                        "otpTtl": RESET_REQUEST_ACCOUNT.window_seconds,
                    },
                )

            ip_counter = self.policy_store.get_counter(
                self._reset_request_ip_key(ip_key)
            )
            if ip_counter >= RESET_REQUEST_IP.threshold:
                raise self._policy_error(
                    "RATE_LIMIT_EXCEEDED",
                    "Demasiadas solicitudes, espera un momento",
                    429,
                    {
                        "policyKey": RESET_REQUEST_IP.key,
                        "threshold": RESET_REQUEST_IP.threshold,
                        "window": RESET_REQUEST_IP.window_label,
                        "counterValue": ip_counter,
                        "lockTtl": RESET_REQUEST_IP.window_seconds,
                    },
                )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def record_reset_request(self, email: str, ip_address: str | None):
        email_key = email.lower()
        ip_key = self._ip_key(ip_address)

        try:
            self.policy_store.increment_counter(
                self._reset_request_account_key(email_key),
                RESET_REQUEST_ACCOUNT.window_seconds,
            )
            self.policy_store.increment_counter(
                self._reset_request_ip_key(ip_key),
                RESET_REQUEST_IP.window_seconds,
            )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def check_verify_code(self, email: str):
        email_key = email.lower()
        try:
            if self.policy_store.is_locked(self._verify_lock_key(email_key)):
                counter = self.policy_store.get_counter(
                    self._verify_counter_key(email_key)
                )
                raise self._policy_error(
                    "ACCOUNT_LOCKED",
                    "Cuenta bloqueada por intentos fallidos",
                    423,
                    {
                        "policyKey": VERIFY_FAIL_LOCK.key,
                        "threshold": VERIFY_FAIL_LOCK.threshold,
                        "window": VERIFY_FAIL_LOCK.window_label,
                        "counterValue": counter,
                        "lockTtl": VERIFY_FAIL_LOCK.lock_ttl_seconds,
                    },
                )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def record_verify_failure(self, email: str):
        email_key = email.lower()
        try:
            counter = self.policy_store.increment_counter(
                self._verify_counter_key(email_key),
                VERIFY_FAIL_LOCK.window_seconds,
            )
            if counter >= VERIFY_FAIL_LOCK.threshold:
                self.policy_store.set_lock(
                    self._verify_lock_key(email_key),
                    VERIFY_FAIL_LOCK.lock_ttl_seconds
                    or VERIFY_FAIL_LOCK.window_seconds,
                )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def record_verify_success(self, email: str):
        email_key = email.lower()
        try:
            self.policy_store.clear_counter(self._verify_counter_key(email_key))
            self.policy_store.clear_counter(self._verify_lock_key(email_key))
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def check_reauth(self, user_id):
        """423 REAUTH_LOCKED si el usuario esta bloqueado para re-autenticar."""
        key = str(user_id)
        try:
            if self.policy_store.is_locked(self._reauth_lock_key(key)):
                counter = self.policy_store.get_counter(self._reauth_counter_key(key))
                raise self._policy_error(
                    "REAUTH_LOCKED",
                    "Demasiados intentos fallidos de confirmacion de identidad",
                    423,
                    {
                        "policyKey": REAUTH_FAIL_LOCK.key,
                        "threshold": REAUTH_FAIL_LOCK.threshold,
                        "window": REAUTH_FAIL_LOCK.window_label,
                        "counterValue": counter,
                        "lockTtl": REAUTH_FAIL_LOCK.lock_ttl_seconds,
                    },
                )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def record_reauth_failure(self, user_id):
        key = str(user_id)
        try:
            counter = self.policy_store.increment_counter(
                self._reauth_counter_key(key),
                REAUTH_FAIL_LOCK.window_seconds,
            )
            if counter >= REAUTH_FAIL_LOCK.threshold:
                self.policy_store.set_lock(
                    self._reauth_lock_key(key),
                    REAUTH_FAIL_LOCK.lock_ttl_seconds or REAUTH_FAIL_LOCK.window_seconds,
                )
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    def record_reauth_success(self, user_id):
        key = str(user_id)
        try:
            self.policy_store.clear_counter(self._reauth_counter_key(key))
            self.policy_store.clear_counter(self._reauth_lock_key(key))
        except PolicyStoreUnavailableError as exc:
            raise self._store_unavailable_error() from exc

    @staticmethod
    def _ip_key(ip_address: str | None) -> str:
        return ip_address or "unknown"

    @staticmethod
    def _login_account_counter_key(username: str) -> str:
        return f"policy:login:account:counter:{username}"

    @staticmethod
    def _login_account_lock_key(username: str) -> str:
        return f"policy:login:account:lock:{username}"

    @staticmethod
    def _login_ip_counter_key(ip_address: str) -> str:
        return f"policy:login:ip:counter:{ip_address}"

    @staticmethod
    def _reset_request_account_key(email: str) -> str:
        return f"policy:reset:request:account:{email}"

    @staticmethod
    def _reset_request_ip_key(ip_address: str) -> str:
        return f"policy:reset:request:ip:{ip_address}"

    @staticmethod
    def _verify_counter_key(email: str) -> str:
        return f"policy:reset:verify:counter:{email}"

    @staticmethod
    def _verify_lock_key(email: str) -> str:
        return f"policy:reset:verify:lock:{email}"

    @staticmethod
    def _reauth_counter_key(user_id: str) -> str:
        return f"policy:reauth:firma:counter:{user_id}"

    @staticmethod
    def _reauth_lock_key(user_id: str) -> str:
        return f"policy:reauth:firma:lock:{user_id}"

    @staticmethod
    def _policy_error(code: str, message: str, status_code: int, policy_meta: dict):
        return AuthServiceError(
            code, message, status_code, details={"policy": policy_meta}
        )

    @staticmethod
    def _store_unavailable_error():
        return AuthServiceError(
            "SERVICE_UNAVAILABLE",
            "Servicio temporalmente no disponible",
            503,
            details={
                "policy": {
                    "policyKey": "policy.enforcement.backend_unavailable",
                    "threshold": 1,
                    "window": "immediate",
                }
            },
        )
