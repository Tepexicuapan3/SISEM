"""
Escritura de BITACORA_SYNC_EXPEDIENTE y BITACORA_REPLICA_SERMED (ver
models.bitacora_sync_expediente).

A diferencia de bitacora_acceso_service (lecturas: un fallo se loguea y se
sigue), aqui la bitacora es condicion para escribir: si no se puede abrir el
registro, la actualizacion no corre; si no se pueden guardar los cambios de
la replica, la replica se revierte. Nunca queda un cambio sin rastro.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.utils import timezone

from apps.administracion.models import BitacoraReplicaSermed, BitacoraSyncExpediente
from apps.authentication.services.response_service import get_client_ip

logger = logging.getLogger(__name__)

# Nombre con que se registra una actualizacion sin usuario (comando, tarea).
PROCESO_SYNC = "SYNC_SERMED"


def abrir(no_exp: str, *, origen: str, usuario=None, request=None) -> BitacoraSyncExpediente:
    """Registra el inicio (EN_CURSO). Si falla, la excepcion sube a proposito."""
    meta = getattr(request, "META", {}) if request is not None else {}
    return BitacoraSyncExpediente.objects.create(
        no_exp=str(no_exp)[:20],
        usuario=usuario,
        cd_usuario=(getattr(usuario, "usuario", None) or PROCESO_SYNC)[:50],
        origen=origen,
        ip_origen=get_client_ip(request) if request is not None else None,
        user_agent=(meta.get("HTTP_USER_AGENT") or "")[:255] or None,
        request_id=(getattr(request, "request_id", None) or None),
    )


def cerrar(registro: BitacoraSyncExpediente, *, resultado: str, conteos: dict | None,
           errores: Iterable[str]) -> None:
    """Cierra el registro una sola vez. Los datos ya quedaron aplicados (o
    revertidos): un fallo aqui se loguea, no cambia lo que paso."""
    registro.resultado = resultado
    registro.fecha_fin = timezone.now()
    registro.conteos = conteos or None
    registro.errores = list(errores) or None
    try:
        registro.save(update_fields=["resultado", "fecha_fin", "conteos", "errores"])
    except Exception:
        logger.exception(
            "No se pudo cerrar la bitacora de sincronizacion %s (%s, resultado %s)",
            registro.pk, registro.no_exp, resultado,
        )


def registrar_cambios_replica(registro: BitacoraSyncExpediente, cambios: Iterable) -> int:
    """Guarda el antes/despues de cada fila que cambio en la replica. Recibe
    los CambioReplica de sync_service. Si falla, la excepcion sube: quien
    llama revierte la replica."""
    filas = [
        BitacoraReplicaSermed(
            sync=registro,
            tabla=cambio.tabla[:40],
            llave=cambio.llave[:120],
            accion=cambio.accion,
            valor_anterior=cambio.anterior,
            valor_nuevo=cambio.nuevo,
        )
        for cambio in cambios
    ]
    BitacoraReplicaSermed.objects.bulk_create(filas, batch_size=500)
    return len(filas)


def ultima_actualizacion(no_exp: str) -> dict | None:
    """La ultima actualizacion que dejo la replica al dia (OK o PARCIAL)."""
    registro = (
        BitacoraSyncExpediente.objects
        .filter(
            no_exp=str(no_exp).strip(),
            resultado__in=[BitacoraSyncExpediente.Resultado.OK, BitacoraSyncExpediente.Resultado.PARCIAL],
        )
        .only("id", "fecha_fin", "fecha_inicio", "cd_usuario", "resultado")
        .order_by("-fecha_inicio", "-id")
        .first()
    )
    if registro is None:
        return None
    return {
        "id_sync": registro.pk,
        "fecha": registro.fecha_fin or registro.fecha_inicio,
        "usuario": registro.cd_usuario,
        "resultado": registro.resultado,
    }
