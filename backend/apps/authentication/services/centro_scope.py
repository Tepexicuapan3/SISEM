"""
Alcance por centro de atención: sobre qué centros opera cada usuario.

Permiso y alcance son ejes separados: el permiso dice QUÉ puede hacer
(recepcion:citas:read) y el alcance SOBRE QUÉ centros. No se crean roles por
centro.

Hoy el alcance es el centro de adscripción (det_usuarios.id_centro_atencion).
Cuando un usuario pueda tener varios centros cambia solo ``_centros_de``; el
resto del sistema ya pregunta "¿qué centros tenés?" y no "¿cuál es tu centro?".

Sin centro asignado no se ve nada (se niega por defecto). El permiso
``alcance:centros:todos`` (o ``*``, el administrador) ve todos los centros.
"""

from dataclasses import dataclass

from django.db.models import Q

PERMISO_TODOS_CENTROS = "alcance:centros:todos"


@dataclass(frozen=True)
class AlcanceCentros:
    todos: bool
    centros: frozenset[int]

    def permite(self, centro_id) -> bool:
        return self.todos or (centro_id is not None and centro_id in self.centros)

    def q(self, campo: str) -> Q:
        """Filtro ORM sobre ``campo`` (id de centro). Sin centros no devuelve filas."""
        if self.todos:
            return Q()
        return Q(**{f"{campo}__in": self.centros})

    @property
    def principal(self) -> int | None:
        """Centro por defecto al registrar algo sin consultorio."""
        return min(self.centros) if len(self.centros) == 1 else None


def centro_principal(id_usuario) -> int | None:
    """Centro de adscripción del usuario, o None si no tiene."""
    if id_usuario is None:
        return None
    from apps.authentication.models import DetUsuario

    return (
        DetUsuario.objects.filter(id_usuario_id=id_usuario)
        .values_list("id_centro_atencion_id", flat=True)
        .first()
    )


def _centros_de(user) -> frozenset[int]:
    centro = centro_principal(getattr(user, "pk", None))
    return frozenset({centro}) if centro is not None else frozenset()


def alcance_contrato(user, permisos) -> dict:
    """``alcanceCentros`` del usuario de sesión (el front avisa si no tiene centro)."""
    from apps.catalogos.models import CatCentroAtencion

    alcance = alcance_de(user, permisos)
    centros = CatCentroAtencion.objects.filter(pk__in=alcance.centros).order_by("name").values("id", "name")
    return {
        "todos": alcance.todos,
        "centros": [{"id": c["id"], "nombre": c["name"]} for c in centros],
    }


def alcance_de(user, permisos=None) -> AlcanceCentros:
    from apps.authentication.services.authorization_service import has_capability

    if permisos is None:
        from apps.authentication.repositories.user_repository import UserRepository

        permisos = UserRepository.build_auth_user(user).get("permissions", [])
    if has_capability(permisos, PERMISO_TODOS_CENTROS):
        return AlcanceCentros(todos=True, centros=frozenset())
    return AlcanceCentros(todos=False, centros=_centros_de(user))
