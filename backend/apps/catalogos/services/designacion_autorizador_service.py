"""Politica unica de autorizacion por designacion (change cancelacion-nota-cascada).

`puede_autorizar(usuario, tipo, centro, fecha)` es el UNICO punto que decide
si un usuario esta habilitado para autorizar un tipo de accion en un centro.
Solo mira el ALCANCE de la designacion (CENTRO / TIPO_CENTRO / GLOBAL); la
adscripcion del usuario (DetUsuario.id_centro_atencion) no interviene.
La verificacion de identidad (password, e-firma) es otra capa:
`authentication.services.firma.VerificadorFirma`.
"""
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from ..repositories.designacion_autorizador_repository import (
    DesignacionAutorizadorRepository,
)


@dataclass(frozen=True)
class DecisionAutorizacion:
    """Resultado de `puede_autorizar`. Se comporta como bool (`if decision:`)."""

    autorizado: bool
    motivo: str = ""
    designacion_id: int | None = None
    alcance_aplicado: str | None = None

    def __bool__(self) -> bool:
        return self.autorizado


MOTIVO_CENTRO_INEXISTENTE = "CENTRO_NO_ENCONTRADO"
MOTIVO_SIN_DESIGNACION = "SIN_DESIGNACION_VIGENTE_QUE_CUBRA_EL_CENTRO"


def puede_autorizar(
    usuario_id: int,
    tipo_codigo: str,
    centro_id: int,
    fecha: date | None = None,
) -> DecisionAutorizacion:
    """True si el usuario tiene una designacion vigente de ese tipo cuyo alcance cubre el centro.

    - Limites de vigencia inclusivos (fe_inicio <= fecha <= fe_fin).
    - GLOBAL sin fe_fin NO habilita (defensa en profundidad; el alta ya lo exige).
    - Una designacion de otro tipo no habilita.
    - Centro inexistente => denegado.
    """
    on_date = fecha or timezone.localdate()

    if not usuario_id or not tipo_codigo or not centro_id:
        return DecisionAutorizacion(False, MOTIVO_SIN_DESIGNACION)

    center_type = DesignacionAutorizadorRepository.get_center_type(centro_id)
    if center_type is None:
        return DecisionAutorizacion(False, MOTIVO_CENTRO_INEXISTENTE)

    scopes = DesignacionAutorizadorRepository.find_covering_scopes(
        user_id=usuario_id,
        type_code=tipo_codigo,
        center_id=centro_id,
        center_type=center_type,
        on_date=on_date,
    )
    if not scopes:
        return DecisionAutorizacion(False, MOTIVO_SIN_DESIGNACION)

    best = scopes[0]  # mas especifico primero (CENTRO > TIPO_CENTRO > GLOBAL)
    return DecisionAutorizacion(
        True,
        designacion_id=best["designation_id"],
        alcance_aplicado=best["scope_type"],
    )
