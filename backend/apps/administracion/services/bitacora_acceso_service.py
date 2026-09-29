"""
Escritura de BITACORA_ACCESO (ver models.bitacora_acceso). Vive en
`administracion` para que cualquier app (consulta_medica, pases,
ambulancias...) registre accesos/exportaciones sin acoplarse entre si.
Nunca rompe la operacion que audita: un fallo se loguea y se sigue.
"""
import logging

from apps.administracion.models import BitacoraAcceso
from apps.authentication.services.response_service import get_client_ip

logger = logging.getLogger(__name__)


def registrar(request, user, *, accion, recurso, no_exp=None, pk_num=None, restringidos=0):
    try:
        BitacoraAcceso.objects.create(
            no_exp=str(no_exp) if no_exp is not None else None,
            tp_paciente=pk_num,
            usuario=user,
            cd_usuario=getattr(user, "usuario", None),
            recurso=recurso,
            accion=accion,
            ip_origen=get_client_ip(request),
            endpoint=(request.path or "")[:255],
            restringidos=restringidos,
        )
    except Exception:
        logger.exception("No se pudo escribir la bitacora de acceso (%s %s)", accion, recurso)


def registrar_exportacion(request, user, *, recurso):
    """Exportacion de un reporte que abarca a varios pacientes (el documento
    pide registrar TODA exportacion)."""
    registrar(request, user, accion=BitacoraAcceso.Accion.EXPORTAR, recurso=recurso)
