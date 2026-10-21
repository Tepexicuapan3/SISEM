from apps.authentication.application.auth_policy_service import AuthPolicyService
from apps.authentication.infrastructure.policy_store import PolicyStore

policy_store = PolicyStore()


def unlock_login(user) -> None:
    # Limpia contador y lock de login por cuenta (no toca claves por IP).
    # Propaga PolicyStoreUnavailableError si Redis no responde.
    username_key = user.usuario.lower()
    policy_store.clear_counter(AuthPolicyService._login_account_lock_key(username_key))
    policy_store.clear_counter(
        AuthPolicyService._login_account_counter_key(username_key)
    )
