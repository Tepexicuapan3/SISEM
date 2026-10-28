"""Quien puede cancelar notas: designacion vieja o modulo de autorizadores (F5).

Interruptor AUTORIZACIONES_NOTA_V2 (apagado por defecto):
- apagado: decide catalogos.puede_autorizar (designacion "CN"), como siempre;
- encendido: decide el contrato publico de apps.autorizaciones (tipo CNO), que
  ademas exige autorizador ACTIVO, vigente y con cedula.
Encenderlo despues de `python manage.py migrar_designaciones --aplicar`.
"""
from dataclasses import dataclass

from django.conf import settings

from apps.autorizaciones import contracts
from apps.catalogos.models.designacion_autorizador import TIPO_CANCELAR_NOTA
from apps.catalogos.services.designacion_autorizador_service import puede_autorizar

CLAVE_TIPO = "CNO"


@dataclass(frozen=True)
class Habilitacion:
    """Se comporta como bool. Trae el registro que habilito al autorizador."""

    autorizado: bool
    alcance_aplicado: str | None = None
    designacion_id: int | None = None
    id_autorizador: int | None = None
    id_autorizador_tipo: int | None = None

    def __bool__(self) -> bool:
        return self.autorizado


def motor_activo() -> bool:
    return bool(getattr(settings, "AUTORIZACIONES_NOTA_V2", False))


def puede_cancelar_notas(id_usuario, id_centro, fecha) -> Habilitacion:
    if motor_activo():
        decision = contracts.puede_autorizar(id_usuario, CLAVE_TIPO, id_centro, fecha=fecha)
        return Habilitacion(
            bool(decision),
            alcance_aplicado=decision.alcance_aplicado,
            id_autorizador=decision.id_autorizador if decision else None,
            id_autorizador_tipo=decision.id_autorizador_tipo,
        )
    decision = puede_autorizar(id_usuario, TIPO_CANCELAR_NOTA, id_centro, fecha)
    return Habilitacion(
        bool(decision), alcance_aplicado=decision.alcance_aplicado, designacion_id=decision.designacion_id,
    )
