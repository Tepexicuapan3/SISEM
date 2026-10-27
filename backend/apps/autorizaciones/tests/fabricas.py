"""Fabricas minimas para las pruebas del modulo de autorizaciones."""
from datetime import date

from django.contrib.auth.hashers import make_password

from apps.authentication.models import DetUsuario, DetUsuarioCedula, SyUsuario
from apps.autorizaciones.models import (
    Autorizador,
    AutorizadorAlcance,
    AutorizadorTipo,
    Motivo,
    TipoAutorizacion,
)
from apps.catalogos.models import CatCentroAtencion

_contador = {"n": 0}


def _siguiente():
    _contador["n"] += 1
    return _contador["n"]


def crear_usuario(con_cedula=True):
    n = _siguiente()
    usuario = SyUsuario.objects.create(
        usuario=f"autorizador_{n}",
        correo=f"autorizador_{n}@example.com",
        clave_hash=make_password("Clave_12345"),
        est_activo=True,
        cambiar_clave=False,
        terminos_acept=True,
    )
    DetUsuario.objects.create(id_usuario=usuario, nombre="Médico", paterno=f"Prueba{n}", materno="")
    if con_cedula:
        DetUsuarioCedula.objects.create(
            id_usuario=usuario, numero=f"CED{n:06d}", tipo="Médico cirujano", es_principal=True, orden=1,
        )
    return usuario


def crear_centro(tipo_centro=CatCentroAtencion.TipoCentro.CLINICA):
    n = _siguiente()
    return CatCentroAtencion.objects.create(name=f"Centro {n}", code=f"CLUES-A{n:04d}", center_type=tipo_centro)


def tipo(clave):
    """Los tipos los siembra la migracion 0002."""
    return TipoAutorizacion.objects.get(clave=clave, fecha_baja__isnull=True)


def motivo(ambito, clave):
    return Motivo.objects.get(ambito=ambito, clave=clave)


def crear_autorizador(usuario=None, *, inicio=date(2026, 1, 1), fin=date(2026, 12, 31), **extra):
    usuario = usuario or crear_usuario()
    return Autorizador.objects.create(
        usuario=usuario,
        fecha_inicio_vigencia=inicio,
        fecha_fin_vigencia=fin,
        **extra,
    )


def asignar_tipo(autorizador, clave="REC", **extra):
    return AutorizadorTipo.objects.create(autorizador=autorizador, tipo_autorizacion=tipo(clave), **extra)


def agregar_alcance(autorizador_tipo, tipo_alcance, valor=None):
    if tipo_alcance == "CENTRO":
        return AutorizadorAlcance.objects.create(
            autorizador_tipo=autorizador_tipo, tipo_alcance="CENTRO", centro_atencion=valor,
        )
    if tipo_alcance == "TIPO_CENTRO":
        return AutorizadorAlcance.objects.create(
            autorizador_tipo=autorizador_tipo, tipo_alcance="TIPO_CENTRO", tipo_centro=valor,
        )
    return AutorizadorAlcance.objects.create(autorizador_tipo=autorizador_tipo, tipo_alcance="GLOBAL")
