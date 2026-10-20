"""
apps/impresion/uses_case/print_document_usecase.py
======================================================
Caso de uso unico de impresion: guarda -> builder -> atomic(reserva de copia,
render, PrintLog, BitacoraAcceso IMPRIMIR) -> AuditoriaEvento post-commit.

Reglas (decisiones del change documentos-imprimibles):
- Render y trazas obligatorias dentro del MISMO ``transaction.atomic``: si el
  render o cualquier traza falla se revierte todo y no se entrega PDF
  (``PRINT_RENDER_ERROR`` / ``PRINT_AUDIT_ERROR``).
- ``log_event`` (AuditoriaEvento) va post-commit y es best-effort.
- El semaforo se toma ANTES de abrir la transaccion para no retener el lock
  del contador de copias mientras se espera cupo.
- No escribe en Oracle ni en tablas clinicas.
"""

import hashlib
import logging
import threading
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.authentication.services.audit_service import log_event
from apps.authentication.services.permission_dependencies import (
    CAPABILITY_REQUIREMENTS,
    evaluate_permission_requirement,
)
from apps.authentication.services.response_service import get_client_ip, get_request_id
from apps.consulta_medica.services.record_access_audit_service import log_print
from apps.impresion import engine
from apps.impresion.errors import PrintError
from apps.impresion.models import PrintLog
from apps.impresion.registry import get_spec
from apps.impresion.repositories.print_log_repository import PrintLogRepository
from apps.impresion.services.branding import resolve_logo_uri
from apps.impresion.services.watermark import resolve_watermarks

logger = logging.getLogger(__name__)

PRINT_TZ = ZoneInfo("America/Mexico_City")
INSTITUTION_NAME = "Servicios Médicos"

_semaphore = None
_semaphore_size = None
_semaphore_lock = threading.Lock()


@dataclass
class PrintResult:
    pdf: bytes
    filename: str
    copy_number: int
    tipo: str
    log_id: int


def _get_semaphore():
    """BoundedSemaphore perezoso del tamano de ``PRINT_MAX_CONCURRENCY``."""
    global _semaphore, _semaphore_size
    size = max(int(getattr(settings, "PRINT_MAX_CONCURRENCY", 2)), 1)
    with _semaphore_lock:
        if _semaphore is None or _semaphore_size != size:
            _semaphore = threading.BoundedSemaphore(size)
            _semaphore_size = size
        return _semaphore


def _ensure_capability(spec, permissions):
    requirement = CAPABILITY_REQUIREMENTS[spec.capability]
    state = evaluate_permission_requirement(requirement, permissions or [])
    if not state["granted"]:
        raise PrintError(
            code="ROLE_NOT_ALLOWED",
            message="No tenes permiso para imprimir este documento.",
            status_code=403,
        )


def _assignment_center_id(user):
    try:
        return user.detalle.id_centro_atencion_id
    except Exception:
        return None


def _ensure_center_access(pctx, user, permissions):
    """R1.5 S5: un usuario asignado a un centro no imprime documentos de otro.

    Solo se rechaza cuando AMBOS centros se conocen y difieren; el comodin
    ``*`` (admin) queda exento.
    """
    if "*" in (permissions or []) or pctx.center_id is None:
        return
    assigned = _assignment_center_id(user)
    if assigned is not None and assigned != pctx.center_id:
        raise PrintError(
            code="ROLE_NOT_ALLOWED",
            message="No tenes acceso a documentos de otro centro de atencion.",
            status_code=403,
        )


def _printed_by(user):
    profile = getattr(user, "detalle", None)
    return getattr(profile, "nombre_completo", None) or getattr(user, "usuario", "") or ""


def _engine_for(spec):
    if spec.legacy_renderer and spec.key == "ficha" and getattr(settings, "FICHA_ENGINE", "weasy") == "docx":
        return "docx"
    return "weasy"


def _render(spec, pctx, user, copy_number, engine_name):
    if engine_name == "docx":
        try:
            return import_string(spec.legacy_renderer)(pctx, user)
        except Exception as exc:
            logger.exception("Fallo el render docx de %s", spec.key)
            raise PrintError(
                code="PRINT_RENDER_ERROR",
                message="No se pudo generar el documento",
                status_code=500,
            ) from exc
    context = dict(pctx.context)
    context.setdefault("institution_name", INSTITUTION_NAME)
    context.setdefault("doc_title", spec.key.capitalize())
    context.update(
        logo_uri=resolve_logo_uri(pctx.legacy_cd_clinica),
        printed_by=_printed_by(user),
        printed_at=timezone.now().astimezone(PRINT_TZ).strftime("%d/%m/%Y %H:%M"),
        copy_number=copy_number,
        watermarks=resolve_watermarks(
            is_cancelled=pctx.is_cancelled,
            copy_number=copy_number,
            watermark_on_reprint=spec.watermark_on_reprint,
        ),
    )
    return engine.render_pdf(spec.template, context)


def _emit_event_best_effort(request, user, spec, resource_id, log_id, copy_number, tipo):
    try:
        log_event(
            request,
            "DocumentPrinted",
            "SUCCESS",
            actor_user=user,
            resource_type="impresion",
            resource_id=resource_id,
            meta={
                "module": "impresion",
                "documento": spec.key,
                "printLogId": log_id,
                "copy": copy_number,
                "tipo": tipo,
            },
        )
    except Exception:
        logger.error(
            "Fallo AuditoriaEvento DocumentPrinted (best-effort) log_id=%s", log_id, exc_info=True
        )


def print_document(*, documento, resource_id, user, permissions, request, roles=None):
    spec = get_spec(documento)
    _ensure_capability(spec, permissions)

    # permisos/roles: la nota redacta diagnosticos sensibles segun quien imprime.
    pctx = import_string(spec.builder)(
        resource_id, user, permissions=permissions or [], roles=roles or []
    )
    _ensure_center_access(pctx, user, permissions)

    semaphore = _get_semaphore()
    timeout = float(getattr(settings, "PRINT_QUEUE_TIMEOUT_S", 15))
    if not semaphore.acquire(timeout=timeout):
        raise PrintError(
            code="PRINT_BUSY",
            message="El servicio de impresion esta ocupado. Intenta de nuevo en unos segundos.",
            status_code=503,
        )
    try:
        engine_name = _engine_for(spec)
        with transaction.atomic():
            copy_number = PrintLogRepository.reserve_copy(spec.key, resource_id)
            pdf = _render(spec, pctx, user, copy_number, engine_name)
            tipo = PrintLog.Tipo.ORIGINAL if copy_number == 1 else PrintLog.Tipo.REIMPRESION
            try:
                log = PrintLogRepository.create_log(
                    documento=spec.key,
                    resource_id=resource_id,
                    folio=pctx.folio or "",
                    no_exp=pctx.no_exp,
                    tp_paciente=str(pctx.pk_num) if pctx.pk_num is not None else None,
                    copy_number=copy_number,
                    tipo=tipo,
                    user=user,
                    user_code=getattr(user, "usuario", "") or "",
                    sha256=hashlib.sha256(pdf).hexdigest(),
                    engine=engine_name,
                    ip=get_client_ip(request),
                    request_id=get_request_id(request) or "",
                    cancelled=pctx.is_cancelled,
                )
                log_print(
                    request,
                    user,
                    no_exp=pctx.no_exp,
                    pk_num=pctx.pk_num,
                    section=spec.section,
                )
            except Exception as exc:
                logger.exception("Fallo la traza obligatoria de impresion %s/%s", spec.key, resource_id)
                raise PrintError(
                    code="PRINT_AUDIT_ERROR",
                    message="No se pudo registrar la impresion. El documento no fue entregado.",
                    status_code=500,
                ) from exc
            transaction.on_commit(
                lambda: _emit_event_best_effort(
                    request, user, spec, resource_id, log.pk, copy_number, tipo
                )
            )
    finally:
        semaphore.release()

    return PrintResult(
        pdf=pdf, filename=pctx.filename, copy_number=copy_number, tipo=tipo, log_id=log.pk
    )
