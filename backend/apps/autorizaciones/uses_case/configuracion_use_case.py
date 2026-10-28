"""Configuracion del modulo de autorizaciones: tipos, reglas por centro y motivos.

Reglas:
  C1  Aprobaciones entre 1 y 10; PRIMERO_VALIDO exige exactamente 1 (tambien la
      combinacion efectiva regla + tipo).
  C2  Horas de vigencia >= 1; en el tipo, el escalamiento ocurre antes del vencimiento.
  C3  Una regla vigente por tipo y centro, con al menos un valor propio; los NULL
      heredan del tipo. La baja es logica.
  C4  Motivos: clave en MAYUSCULAS_CON_GUION_BAJO, unica por ambito e inmutable;
      no se desactiva el ultimo motivo activo de un ambito.
  C5  Toda edicion exige la `version` vigente; cada mutacion se audita en la misma
      transaccion (si la auditoria falla, se revierte).
Un cambio solo afecta a solicitudes NUEVAS: cada solicitud guarda sus reglas al crearse.
"""
from __future__ import annotations

import re
from typing import Callable

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import Modalidad, Motivo, ReglaCentro, TipoAutorizacion
from ..repositories.configuracion_repository import ConfiguracionRepository as Repo

Auditoria = Callable[..., None]

# Campos editables del tipo: {campo de la API: campo del modelo}.
CAMPOS_TIPO = {
    "modalidadPredeterminada": "modalidad_predeterminada",
    "aprobacionesRequeridas": "aprobaciones_requeridas",
    "rechazoResuelveSolicitud": "rechazo_resuelve_solicitud",
    "permiteRechazo": "permite_rechazo",
    "horasVigenciaSolicitud": "horas_vigencia_solicitud",
    "horasEscalamiento": "horas_escalamiento",
    "requiereCedula": "requiere_cedula",
}
CAMPOS_REGLA = {
    "modalidad": "modalidad",
    "aprobacionesRequeridas": "aprobaciones_requeridas",
    "horasVigenciaSolicitud": "horas_vigencia_solicitud",
}
_CLAVE_VALIDA = re.compile(r"^[A-Z0-9_]{2,20}$")


class ConfiguracionError(Exception):
    def __init__(self, code: str, message: str, http_status: int, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _invalido(campo, mensaje):
    return ConfiguracionError("CONFIG_INVALID", mensaje, 400, {campo: [mensaje]})


def tipo_a_dict(tipo: TipoAutorizacion) -> dict:
    datos = {api: getattr(tipo, campo) for api, campo in CAMPOS_TIPO.items()}
    return {"id": tipo.pk, "clave": tipo.clave, "nombre": tipo.nombre, "version": tipo.version, **datos}


def regla_a_dict(regla: ReglaCentro) -> dict:
    datos = {api: getattr(regla, campo) for api, campo in CAMPOS_REGLA.items()}
    return {
        "id": regla.pk,
        "tipoId": regla.tipo_autorizacion_id,
        "claveTipo": regla.tipo_autorizacion.clave,
        "centroId": regla.centro_atencion_id,
        "centroNombre": regla.centro_atencion.name,
        "version": regla.version,
        **datos,
    }


def motivo_a_dict(motivo: Motivo) -> dict:
    return {
        "id": motivo.pk,
        "ambito": motivo.ambito,
        "clave": motivo.clave,
        "descripcion": motivo.descripcion,
        "requiereDescripcionLibre": motivo.requiere_descripcion_libre,
        "activo": motivo.esta_activo,
        "version": motivo.version,
    }


def _validar_aprobaciones(modalidad, aprobaciones, campo="aprobacionesRequeridas"):
    if aprobaciones is None:
        return
    if not 1 <= aprobaciones <= 10:
        raise _invalido(campo, "Las aprobaciones requeridas van de 1 a 10")
    if modalidad == Modalidad.PRIMERO_VALIDO and aprobaciones != 1:
        raise _invalido(campo, "Con «primero válido» basta una aprobación")


def _validar_horas(vigencia, escalamiento):
    if vigencia is not None and vigencia < 1:
        raise _invalido("horasVigenciaSolicitud", "La vigencia debe ser de al menos 1 hora")
    if escalamiento is not None and escalamiento < 1:
        raise _invalido("horasEscalamiento", "El escalamiento debe ser de al menos 1 hora")
    if vigencia is not None and escalamiento is not None and escalamiento >= vigencia:
        raise _invalido("horasEscalamiento", "El escalamiento debe ocurrir antes de que venza la solicitud")


def _validar_modalidad(modalidad, campo):
    if modalidad is not None and modalidad not in Modalidad.values:
        raise _invalido(campo, f"Modalidad inválida; permitidas: {', '.join(Modalidad.values)}")


def _exigir_version(registro, datos):
    if datos.get("version") != registro.version:
        raise ConfiguracionError(
            "STALE_VERSION",
            "Otro usuario modificó este registro. Recarga la información e intenta de nuevo.",
            409,
            {"versionActual": registro.version},
        )


def _marcar_modificado(registro, actor_id):
    registro.version += 1
    registro.fecha_modificacion = timezone.now()
    registro.id_usuario_modificacion = actor_id


class ConfiguracionUseCase:

    # ------------------------------------------------------------------ #
    # Tipos                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def actualizar_tipo(id_tipo, datos: dict, *, actor_id, auditoria: Auditoria) -> TipoAutorizacion:
        with transaction.atomic():
            tipo = Repo.tipo_para_actualizar(id_tipo)
            if tipo is None:
                raise ConfiguracionError("TYPE_NOT_FOUND", "Tipo de autorización no encontrado", 404)
            _exigir_version(tipo, datos)
            antes = tipo_a_dict(tipo)
            for api, campo in CAMPOS_TIPO.items():
                if api in datos and datos[api] is not None:
                    setattr(tipo, campo, datos[api])
            _validar_modalidad(tipo.modalidad_predeterminada, "modalidadPredeterminada")
            _validar_aprobaciones(tipo.modalidad_predeterminada, tipo.aprobaciones_requeridas)
            _validar_horas(tipo.horas_vigencia_solicitud, tipo.horas_escalamiento)
            _marcar_modificado(tipo, actor_id)
            tipo.save()
            auditoria("ConfigTipoActualizado", tipo.pk, antes, tipo_a_dict(tipo))
        return tipo

    # ------------------------------------------------------------------ #
    # Reglas por centro                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validar_regla(regla: ReglaCentro):
        valores = [getattr(regla, campo) for campo in CAMPOS_REGLA.values()]
        if all(v is None for v in valores):
            raise _invalido("modalidad", "Define al menos un valor propio para el centro")
        _validar_modalidad(regla.modalidad, "modalidad")
        tipo = regla.tipo_autorizacion
        modalidad = regla.modalidad or tipo.modalidad_predeterminada
        _validar_aprobaciones(modalidad, regla.aprobaciones_requeridas or tipo.aprobaciones_requeridas)
        # El escalamiento es del tipo: con una vigencia de centro mas corta, la solicitud vence sin escalar.
        _validar_horas(regla.horas_vigencia_solicitud, None)

    @staticmethod
    def crear_regla(datos: dict, *, actor_id, auditoria: Auditoria) -> ReglaCentro:
        tipo = Repo.tipo(datos.get("tipoId"))
        if tipo is None:
            raise _invalido("tipoId", "Tipo de autorización no encontrado")
        if not Repo.existe_centro(datos.get("centroId")):
            raise _invalido("centroId", "Centro de atención no encontrado")
        regla = ReglaCentro(
            tipo_autorizacion=tipo, centro_atencion_id=datos["centroId"], id_usuario_creacion=actor_id,
            **{campo: datos.get(api) for api, campo in CAMPOS_REGLA.items()},
        )
        ConfiguracionUseCase._validar_regla(regla)
        if Repo.existe_regla_vigente(tipo.pk, datos["centroId"]):
            raise ConfiguracionError(
                "RULE_EXISTS", "Ya hay una regla vigente para este tipo y centro; edítala en su lugar", 409,
            )
        try:
            with transaction.atomic():
                regla.save()
                auditoria("ReglaCentroCreada", regla.pk, None, regla_a_dict(regla))
        except IntegrityError as exc:  # carrera con otra alta del mismo tipo y centro
            raise ConfiguracionError(
                "RULE_EXISTS", "Ya hay una regla vigente para este tipo y centro; edítala en su lugar", 409,
            ) from exc
        return regla

    @staticmethod
    def _regla_bloqueada(id_regla, datos):
        regla = Repo.regla_para_actualizar(id_regla)
        if regla is None:
            raise ConfiguracionError("RULE_NOT_FOUND", "Regla no encontrada", 404)
        _exigir_version(regla, datos)
        return regla

    @staticmethod
    def actualizar_regla(id_regla, datos: dict, *, actor_id, auditoria: Auditoria) -> ReglaCentro:
        with transaction.atomic():
            regla = ConfiguracionUseCase._regla_bloqueada(id_regla, datos)
            antes = regla_a_dict(regla)
            # En la regla, null es valido: vuelve a heredar del tipo.
            for api, campo in CAMPOS_REGLA.items():
                if api in datos:
                    setattr(regla, campo, datos[api])
            ConfiguracionUseCase._validar_regla(regla)
            _marcar_modificado(regla, actor_id)
            regla.save()
            auditoria("ReglaCentroActualizada", regla.pk, antes, regla_a_dict(regla))
        return regla

    @staticmethod
    def dar_baja_regla(id_regla, datos: dict, *, actor_id, auditoria: Auditoria) -> ReglaCentro:
        with transaction.atomic():
            regla = ConfiguracionUseCase._regla_bloqueada(id_regla, datos)
            antes = regla_a_dict(regla)
            ahora = timezone.now()
            _marcar_modificado(regla, actor_id)
            regla.esta_activo = False
            regla.fecha_baja = ahora
            regla.id_usuario_baja = actor_id
            regla.save()
            auditoria("ReglaCentroBaja", regla.pk, antes, None)
        return regla

    # ------------------------------------------------------------------ #
    # Motivos                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def crear_motivo(datos: dict, *, actor_id, auditoria: Auditoria) -> Motivo:
        ambito = datos.get("ambito")
        if ambito not in Motivo.Ambito.values:
            raise _invalido("ambito", f"Ámbito inválido; permitidos: {', '.join(Motivo.Ambito.values)}")
        clave = re.sub(r"\s+", "_", (datos.get("clave") or "").strip()).upper()
        if not _CLAVE_VALIDA.match(clave):
            raise _invalido("clave", "La clave lleva de 2 a 20 letras, números o guion bajo")
        descripcion = (datos.get("descripcion") or "").strip()
        if not descripcion:
            raise _invalido("descripcion", "La descripción es obligatoria")
        if Repo.existe_motivo(ambito, clave):
            raise ConfiguracionError("REASON_EXISTS", "Ya existe un motivo con esa clave en este ámbito", 409)
        try:
            with transaction.atomic():
                motivo = Motivo.objects.create(
                    ambito=ambito, clave=clave, descripcion=descripcion[:150],
                    requiere_descripcion_libre=bool(datos.get("requiereDescripcionLibre")),
                    id_usuario_creacion=actor_id,
                )
                auditoria("MotivoCreado", motivo.pk, None, motivo_a_dict(motivo))
        except IntegrityError as exc:
            raise ConfiguracionError("REASON_EXISTS", "Ya existe un motivo con esa clave en este ámbito", 409) from exc
        return motivo

    @staticmethod
    def actualizar_motivo(id_motivo, datos: dict, *, actor_id, auditoria: Auditoria) -> Motivo:
        with transaction.atomic():
            motivo = Repo.motivo_para_actualizar(id_motivo)
            if motivo is None:
                raise ConfiguracionError("REASON_NOT_FOUND", "Motivo no encontrado", 404)
            _exigir_version(motivo, datos)
            antes = motivo_a_dict(motivo)
            # La clave no se edita: las decisiones y movimientos ya firmados la referencian.
            if "descripcion" in datos:
                descripcion = (datos.get("descripcion") or "").strip()
                if not descripcion:
                    raise _invalido("descripcion", "La descripción es obligatoria")
                motivo.descripcion = descripcion[:150]
            if "requiereDescripcionLibre" in datos:
                motivo.requiere_descripcion_libre = bool(datos["requiereDescripcionLibre"])
            if "activo" in datos and bool(datos["activo"]) != motivo.esta_activo:
                if not datos["activo"] and Repo.activos_en_ambito(motivo.ambito) <= 1:
                    raise ConfiguracionError(
                        "LAST_ACTIVE_REASON", "Debe quedar al menos un motivo activo en este ámbito", 409,
                    )
                motivo.esta_activo = bool(datos["activo"])
            _marcar_modificado(motivo, actor_id)
            motivo.save()
            auditoria("MotivoActualizado", motivo.pk, antes, motivo_a_dict(motivo))
        return motivo
