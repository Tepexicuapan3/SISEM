"""
Fábrica compartida de médicos para tests.

Desde `medicos-legado-archivo` todo `CatMedico` exige un usuario
(`id_usuario` NOT NULL) y su nombre sale de `DetUsuario`. Esta función crea
`SyUsuario` + `DetUsuario` + `CatMedico` en un paso para no repetirlo en cada
suite. `DetUsuario.nombre_completo` es un GeneratedField: no se asigna.
"""
import itertools

from django.contrib.auth.hashers import make_password

from apps.authentication.models import DetUsuario, SyUsuario
from apps.medicos.models import CatMedico

_contador = itertools.count(1)


def crear_usuario_medico(*, nombre="Medico", paterno="Prueba", materno=None, usuario=None, **det_extra):
    """SyUsuario + DetUsuario (sin CatMedico). Devuelve el SyUsuario."""
    n = next(_contador)
    username = usuario or f"dr_test_{n}"
    user = SyUsuario.objects.create(
        usuario=username,
        correo=f"{username}@example.com",
        clave_hash=make_password("x"),
        est_activo=True,
    )
    DetUsuario.objects.create(
        id_usuario=user, nombre=nombre, paterno=paterno, materno=materno, **det_extra,
    )
    return user


def crear_medico(*, id=None, nombre="Medico", paterno="Prueba", materno=None, usuario=None, **campos):
    """
    CatMedico con su usuario. `id` fija el No. Médico (opcional); `usuario`
    reutiliza un SyUsuario existente (si no, se crea uno con
    `nombre/paterno/materno`); `campos` pasa tipo_medico, servicio, etc.
    """
    if usuario is None or isinstance(usuario, str):
        usuario = crear_usuario_medico(
            nombre=nombre, paterno=paterno, materno=materno, usuario=usuario,
        )
    if id is not None:
        campos["id"] = id
    return CatMedico.objects.create(id_usuario=usuario, **campos)
