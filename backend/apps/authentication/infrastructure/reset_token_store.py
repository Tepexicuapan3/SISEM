from __future__ import annotations

from django.core.cache import cache

from apps.authentication.services.errors import PolicyStoreUnavailableError


class ResetTokenStore:
    def mark_consumed(self, jti: str, ttl_seconds: int) -> bool:
        # cache.add es atomico (SET NX): True solo para el primer uso del jti.
        try:
            return bool(cache.add(self._key(jti), 1, ttl_seconds))
        except Exception as exc:
            raise PolicyStoreUnavailableError("Policy store unavailable") from exc

    @staticmethod
    def _key(jti: str) -> str:
        return f"auth:reset:jti:consumed:{jti}"
