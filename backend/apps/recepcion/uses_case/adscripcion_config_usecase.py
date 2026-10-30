"""
P-03 · Configuración de la adscripción: equivalencias de clínica de SERMED a
centro de SIRES y consultorios que reciben pacientes familiares. La usa el
administrador; cada cambio queda auditado con antes y después.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalogos.models import CatCentroAtencion, Consultorios
from apps.recepcion.models import AdscripcionClinicaCentro, AdscripcionConsultorio
from apps.recepcion.uses_case.adscripcion_usecase import AdscripcionError, Operador, _auditar


def _foto_equivalencia(e) -> dict:
    return {"claveClinicaSermed": e.clave_clinica_sermed, "idCentroAtencion": e.centro_id, "estaActivo": e.esta_activo}


def _foto_consultorio(c) -> dict:
    return {"idConsultorio": c.consultorio_id, "capacidadMaxima": c.capacidad_maxima, "estaActivo": c.esta_activo}


def _exigir_centro(id_centro):
    if not CatCentroAtencion.objects.filter(pk=id_centro).exists():
        raise AdscripcionError("CENTRO_NO_ENCONTRADO", "Centro de atención no encontrado.", 404)


def _exigir_capacidad(capacidad):
    if capacidad is not None and capacidad <= 0:
        raise AdscripcionError("CAPACIDAD_INVALIDA", "La capacidad tiene que ser mayor a cero o quedar vacía.", 422)


# ── Equivalencias de clínica ────────────────────────────────────────────────

def crear_equivalencia(*, clave_clinica_sermed, id_centro_atencion, operador: Operador, request):
    clave = (clave_clinica_sermed or "").strip()
    if not clave:
        raise AdscripcionError("CLAVE_REQUERIDA", "Escriba la clave de la clínica en SERMED.", 422)
    _exigir_centro(id_centro_atencion)
    with transaction.atomic():
        try:
            with transaction.atomic():
                equivalencia = AdscripcionClinicaCentro.objects.create(
                    clave_clinica_sermed=clave, centro_id=id_centro_atencion,
                    id_usuario_creacion=operador.id_usuario,
                )
        except IntegrityError as exc:
            raise AdscripcionError(
                "CLAVE_DUPLICADA", f"La clínica {clave} de SERMED ya tiene un centro asignado.", 409,
            ) from exc
        _auditar(
            request, operador, "ADSCRIPCION_EQUIVALENCIA", "SUCCESS", recurso_id=equivalencia.id,
            despues=_foto_equivalencia(equivalencia), estricto=True,
        )
        return equivalencia


def actualizar_equivalencia(*, id_clinica_centro, cambios: dict, operador: Operador, request):
    with transaction.atomic():
        equivalencia = AdscripcionClinicaCentro.objects.select_for_update().filter(pk=id_clinica_centro).first()
        if equivalencia is None:
            raise AdscripcionError("EQUIVALENCIA_NO_ENCONTRADA", "Equivalencia no encontrada.", 404)
        antes = _foto_equivalencia(equivalencia)
        if "id_centro_atencion" in cambios:
            _exigir_centro(cambios["id_centro_atencion"])
            equivalencia.centro_id = cambios["id_centro_atencion"]
        if "esta_activo" in cambios:
            equivalencia.esta_activo = cambios["esta_activo"]
        equivalencia.fecha_modificacion = timezone.now()
        equivalencia.id_usuario_modificacion = operador.id_usuario
        equivalencia.save()
        _auditar(
            request, operador, "ADSCRIPCION_EQUIVALENCIA", "SUCCESS", recurso_id=equivalencia.id,
            antes=antes, despues=_foto_equivalencia(equivalencia), estricto=True,
        )
        return equivalencia


# ── Consultorios familiares ─────────────────────────────────────────────────

def crear_consultorio_familiar(*, consultorio_id, capacidad_maxima, operador: Operador, request):
    _exigir_capacidad(capacidad_maxima)
    if not Consultorios.objects.filter(pk=consultorio_id, is_active=True, deleted_at__isnull=True).exists():
        raise AdscripcionError("CONSULTORIO_NO_ENCONTRADO", "Consultorio no encontrado o inactivo.", 404)
    with transaction.atomic():
        try:
            with transaction.atomic():
                config = AdscripcionConsultorio.objects.create(
                    consultorio_id=consultorio_id, capacidad_maxima=capacidad_maxima,
                    id_usuario_creacion=operador.id_usuario,
                )
        except IntegrityError as exc:
            raise AdscripcionError(
                "CONSULTORIO_YA_CONFIGURADO", "Ese consultorio ya está configurado como familiar.", 409,
            ) from exc
        _auditar(
            request, operador, "ADSCRIPCION_CONSULTORIO", "SUCCESS", recurso_id=config.id,
            despues=_foto_consultorio(config), estricto=True,
        )
        return config


def actualizar_consultorio_familiar(*, id_adscripcion_consultorio, cambios: dict, operador: Operador, request):
    if "capacidad_maxima" in cambios:
        _exigir_capacidad(cambios["capacidad_maxima"])
    with transaction.atomic():
        config = AdscripcionConsultorio.objects.select_for_update().filter(pk=id_adscripcion_consultorio).first()
        if config is None:
            raise AdscripcionError("CONFIGURACION_NO_ENCONTRADA", "Configuración no encontrada.", 404)
        antes = _foto_consultorio(config)
        if "capacidad_maxima" in cambios:
            config.capacidad_maxima = cambios["capacidad_maxima"]
        if "esta_activo" in cambios:
            config.esta_activo = cambios["esta_activo"]
        config.fecha_modificacion = timezone.now()
        config.id_usuario_modificacion = operador.id_usuario
        config.save()
        _auditar(
            request, operador, "ADSCRIPCION_CONSULTORIO", "SUCCESS", recurso_id=config.id,
            antes=antes, despues=_foto_consultorio(config), estricto=True,
        )
        return config
