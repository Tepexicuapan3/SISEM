"""Verificacion de identidad para acciones firmadas (change cancelacion-nota-cascada).

`VerificadorFirma` es el punto de extension: hoy solo existe
`VerificadorSimple` (re-autenticacion con la contrasena PROPIA del actor);
una e-firma real (SAT) seria otra implementacion del mismo Protocol, sin
tocar a los casos de uso que lo consumen.

Errores (AuthServiceError, mismo contrato que el resto de authentication):
  - 403 REAUTH_FAILED   contrasena incorrecta o ausente. NUNCA 401: el
                        interceptor del frontend hace refresh/logout en 401.
  - 423 REAUTH_LOCKED   bloqueo por intentos fallidos (PolicyRule
                        REAUTH_FAIL_LOCK, clave por id_usuario). Mientras dura,
                        ni la contrasena correcta desbloquea.
  - 503 SERVICE_UNAVAILABLE  el PolicyStore (cache) no responde: se falla
                        cerrado, no se permite firmar sin control de intentos.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from django.utils import timezone

from apps.authentication.application.auth_policy_service import AuthPolicyService
from apps.authentication.repositories.user_repository import UserRepository
from apps.authentication.services.errors import AuthServiceError

METODO_FIRMA_SIMPLE = "SIMPLE"


@dataclass(frozen=True)
class ResultadoFirma:
    metodo: str
    hash_contenido: str
    firmado_en: datetime


@runtime_checkable
class VerificadorFirma(Protocol):
    def verificar(
        self, usuario, credencial: str | None, contenido_canonico: bytes | str
    ) -> ResultadoFirma:
        """Verifica la identidad de `usuario` con `credencial` y sella `contenido_canonico`.

        Lanza AuthServiceError si la verificacion falla.
        """
        ...


def _to_bytes(contenido: bytes | str) -> bytes:
    return contenido.encode("utf-8") if isinstance(contenido, str) else contenido


class VerificadorSimple:
    """Re-autenticacion con la contrasena propia del actor + rate limit."""

    metodo = METODO_FIRMA_SIMPLE

    def __init__(self, policy_service: AuthPolicyService | None = None, password_checker=None):
        self.policy_service = policy_service or AuthPolicyService()
        self._verify_password = password_checker or UserRepository.verify_password

    def verificar(self, usuario, credencial, contenido_canonico) -> ResultadoFirma:
        user_id = usuario.id_usuario

        # 1. Bloqueo vigente: se corta ANTES de mirar la contrasena (no hay
        #    oraculo de contrasena mientras dure el bloqueo).
        self.policy_service.check_reauth(user_id)

        # 2. Contrasena propia. Vacia/ausente cuenta como intento fallido.
        if not credencial or not self._verify_password(usuario, credencial):
            self.policy_service.record_reauth_failure(user_id)
            raise AuthServiceError(
                "REAUTH_FAILED",
                "No se pudo confirmar tu identidad",
                403,
            )

        self.policy_service.record_reauth_success(user_id)
        return ResultadoFirma(
            metodo=self.metodo,
            hash_contenido=hashlib.sha256(_to_bytes(contenido_canonico)).hexdigest(),
            firmado_en=timezone.now(),
        )
