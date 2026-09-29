"""
BITACORA_ACCESO (documento "Historia Clinica Unificada", controles de datos
sensibles): quien VIO, IMPRIMIO, EXPORTO o MODIFICO la historia de cada
paciente, en su propia tabla (`administracion.BitacoraAcceso`).

Deduplicacion de lecturas: el frontend (TanStack Query) refetchea cada tab
al reenfocar la ventana -- sin filtro, una sola lectura generaria decenas de
filas identicas. Se registra como maximo UN "ver" por (actor, no_exp,
pk_num, recurso) cada `ACCESS_DEDUP_WINDOW_SECONDS` (`cache.add`, atomico en
Redis). Si la cache no responde, se registra igual: mejor duplicar que
perder un acceso. Las modificaciones, exportaciones y lecturas con
diagnosticos restringidos NO se deduplican.

Nunca bloquea la operacion: un fallo al escribir la bitacora se loguea y
se sigue (mismo criterio que antes con auditoria_eventos).
"""
import logging

from django.core.cache import cache

from apps.administracion.models import BitacoraAcceso
from apps.administracion.services.bitacora_acceso_service import registrar, registrar_exportacion

logger = logging.getLogger(__name__)

ACCESS_DEDUP_WINDOW_SECONDS = 300


class RecordSection:
    CLINICAL_HISTORY = "historia_clinica"
    PATIENT_PROFILE = "ficha_paciente"
    STOMATOLOGY_HISTORY = "estomatologia"
    ALLERGIES = "alergias"
    CONSULTATIONS = "consultas"
    LEGACY_CONSULTATIONS = "consultas_legado"
    ODONTOGRAM = "odontograma"
    MEDICAL_LEAVES = "incapacidades"
    STUDY_RESULTS = "estudios"
    PERSONAL_HISTORY = "antecedentes_personales"
    FAMILY_HISTORY = "antecedentes_familiares"
    SURGICAL_HISTORY = "antecedentes_quirurgicos"
    HABITS = "habitos"
    DENTAL_TREATMENTS = "tratamientos_dentales"
    HISTORICAL_NOTES = "notas_historicas"
    DAILY_REPORT = "reporte_consultas_diario"
    MEDICAL_LEAVE_REPORT = "reporte_incapacidades"

    ALL = (
        CLINICAL_HISTORY,
        PATIENT_PROFILE,
        STOMATOLOGY_HISTORY,
        ALLERGIES,
        CONSULTATIONS,
        LEGACY_CONSULTATIONS,
        ODONTOGRAM,
        MEDICAL_LEAVES,
        STUDY_RESULTS,
        PERSONAL_HISTORY,
        FAMILY_HISTORY,
        SURGICAL_HISTORY,
        HABITS,
        DENTAL_TREATMENTS,
        HISTORICAL_NOTES,
        DAILY_REPORT,
        MEDICAL_LEAVE_REPORT,
    )


def _dedup_key(actor_id, no_exp, pk_num, section):
    return f"expediente-access:{actor_id}:{no_exp}:{pk_num}:{section}"


def _should_log(actor_id, no_exp, pk_num, section):
    try:
        return cache.add(
            _dedup_key(actor_id, no_exp, pk_num, section),
            1,
            timeout=ACCESS_DEDUP_WINDOW_SECONDS,
        )
    except Exception:
        logger.warning("Cache no disponible para deduplicar bitacora de acceso", exc_info=True)
        return True


def _write(request, user, *, accion, recurso, no_exp=None, pk_num=None, restringidos=0):
    registrar(
        request, user, accion=accion, recurso=recurso,
        no_exp=no_exp, pk_num=pk_num, restringidos=restringidos,
    )


def log_patient_record_access(request, user, *, actor_id, no_exp, pk_num, section):
    """accion = ver (deduplicado por ventana)."""
    if not _should_log(actor_id, no_exp, pk_num, section):
        return
    _write(request, user, accion=BitacoraAcceso.Accion.VER, recurso=section, no_exp=no_exp, pk_num=pk_num)


def log_restricted_access(request, user, *, no_exp, pk_num, section, restricted_count):
    """accion = ver con diagnosticos restringidos (sin deduplicar)."""
    _write(
        request, user, accion=BitacoraAcceso.Accion.VER, recurso=section,
        no_exp=no_exp, pk_num=pk_num, restringidos=restricted_count,
    )


def log_patient_record_change(request, user, *, no_exp, pk_num, section):
    """accion = modificar (sin deduplicar)."""
    _write(request, user, accion=BitacoraAcceso.Accion.MODIFICAR, recurso=section, no_exp=no_exp, pk_num=pk_num)


def log_export(request, user, *, section):
    """accion = exportar, de un reporte que abarca a varios pacientes."""
    registrar_exportacion(request, user, recurso=section)
