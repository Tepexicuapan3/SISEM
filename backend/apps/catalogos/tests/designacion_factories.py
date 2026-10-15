"""Fabricas minimas para los tests de designacion de autorizadores."""
from datetime import date

from django.contrib.auth.hashers import make_password

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import (
    CatCentroAtencion,
    DesignacionAlcance,
    DesignacionAutorizador,
    TpAutorizacion,
)
from apps.catalogos.models.designacion_autorizador import TIPO_CANCELAR_NOTA

_counter = {"n": 0}


def _next():
    _counter["n"] += 1
    return _counter["n"]


def make_user(username=None, password="Clave_12345"):
    n = _next()
    user = SyUsuario.objects.create(
        usuario=username or f"auth_user_{n}",
        correo=f"auth_user_{n}@example.com",
        clave_hash=make_password(password),
        est_activo=True,
        cambiar_clave=False,
        terminos_acept=True,
    )
    DetUsuario.objects.create(id_usuario=user, nombre="Nombre", paterno=f"Apellido{n}", materno="")
    return user


def make_center(center_type=CatCentroAtencion.TipoCentro.CLINICA, name=None):
    n = _next()
    return CatCentroAtencion.objects.create(
        name=name or f"Centro {n}",
        code=f"CLUES-T{n:04d}",
        center_type=center_type,
    )


def get_tipo(code=TIPO_CANCELAR_NOTA, name=None):
    """Devuelve el tipo por codigo; lo crea si no existe (la migracion 0038 ya siembra CN)."""
    tipo = TpAutorizacion.objects.filter(code=code).first()
    if tipo is None:
        tipo = TpAutorizacion.objects.create(code=code, name=name or f"Tipo {code}")
    return tipo


def make_designation(user=None, tipo=None, *, start=None, end=None, scopes=(), position="Director", **extra):
    """scopes: iterable de ("CENTRO", center) | ("TIPO_CENTRO", "CLINICA") | ("GLOBAL", None)."""
    user = user or make_user()
    tipo = tipo or get_tipo()
    designation = DesignacionAutorizador.objects.create(
        user=user,
        authorization_type=tipo,
        position=position,
        start_date=start or date(2020, 1, 1),
        end_date=end,
        **extra,
    )
    for scope_type, value in scopes:
        add_scope(designation, scope_type, value)
    return designation


def add_scope(designation, scope_type, value=None):
    if scope_type == "CENTRO":
        return DesignacionAlcance.objects.create(designation=designation, scope_type="CENTRO", center=value)
    if scope_type == "TIPO_CENTRO":
        return DesignacionAlcance.objects.create(designation=designation, scope_type="TIPO_CENTRO", center_type=value)
    return DesignacionAlcance.objects.create(designation=designation, scope_type="GLOBAL")
