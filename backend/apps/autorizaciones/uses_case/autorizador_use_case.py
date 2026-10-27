"""Administracion de autorizadores medicos (plan autorizadores-medicos, reglas A1-A10).

  A1  Usuario existente y activo; un solo autorizador vigente por usuario.
  A2  Si algun tipo exige cedula, el usuario la tiene capturada en Usuarios.
  A3  Fin >= inicio; la vigencia de cada tipo cae dentro de la del autorizador.
  A4  Cada tipo tiene al menos un alcance; GLOBAL exige su permiso.
  A5  Retirar un tipo o centro es baja logica (el historial se conserva).
  A6  Suspender o dar de baja exige motivo; la baja es terminal.
  A7  Renovar solo amplia la fecha de fin.
  A10 Nadie administra su propio registro de autorizador.

Cada mutacion corre en una transaccion junto con su movimiento de historial y
su evento de auditoria (`auditoria(accion, id, antes, despues)`): si la
auditoria falla, se revierte todo. Toda edicion exige la `version` vigente.
"""
from __future__ import annotations

from typing import Callable

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import (
    TIPOS_CENTRO_VALIDOS,
    Autorizador,
    AutorizadorAlcance,
    AutorizadorTipo,
    Motivo,
)
from ..repositories.autorizador_repository import AutorizadorRepository as Repo

Auditoria = Callable[..., None]

CENTRO = AutorizadorAlcance.TipoAlcance.CENTRO
TIPO_CENTRO = AutorizadorAlcance.TipoAlcance.TIPO_CENTRO
GLOBAL = AutorizadorAlcance.TipoAlcance.GLOBAL


class AutorizadorError(Exception):
    """Error de negocio con contrato HTTP (code, message, http_status, details)."""

    def __init__(self, code: str, message: str, http_status: int, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _validacion(details: dict) -> AutorizadorError:
    return AutorizadorError("VALIDATION_ERROR", "Datos de entrada inválidos", 400, details)


# ---------------------------------------------------------------------- #
# Snapshots (historial y auditoria; sin datos sensibles)                  #
# ---------------------------------------------------------------------- #

def _iso(valor):
    return valor.isoformat() if valor else None


def _clave_alcance(tipo_alcance, id_centro, tipo_centro):
    return (tipo_alcance, id_centro, tipo_centro)


def snapshot(autorizador: Autorizador) -> dict:
    tipos = Repo.tipos_activos(autorizador.pk)
    alcances = Repo.alcances_activos([t.pk for t in tipos])
    return {
        "id": autorizador.pk,
        "usuarioId": autorizador.usuario_id,
        "estatus": autorizador.estatus,
        "fechaInicioVigencia": _iso(autorizador.fecha_inicio_vigencia),
        "fechaFinVigencia": _iso(autorizador.fecha_fin_vigencia),
        "cargo": autorizador.cargo,
        "numeroOficio": autorizador.numero_oficio,
        "motivoEstatusId": autorizador.motivo_estatus_id,
        "fechaFinSuspension": _iso(autorizador.fecha_fin_suspension),
        "version": autorizador.version,
        "tipos": [
            {
                "clave": t.tipo_autorizacion.clave,
                "fechaInicioVigencia": _iso(t.fecha_inicio_vigencia),
                "fechaFinVigencia": _iso(t.fecha_fin_vigencia),
                "alcance": {
                    "centros": sorted(
                        a.centro_atencion_id for a in alcances
                        if a.autorizador_tipo_id == t.pk and a.tipo_alcance == CENTRO
                    ),
                    "tiposCentro": sorted(
                        a.tipo_centro for a in alcances
                        if a.autorizador_tipo_id == t.pk and a.tipo_alcance == TIPO_CENTRO
                    ),
                    "global": any(
                        a.autorizador_tipo_id == t.pk and a.tipo_alcance == GLOBAL for a in alcances
                    ),
                },
            }
            for t in tipos
        ],
    }


# ---------------------------------------------------------------------- #
# Validaciones                                                           #
# ---------------------------------------------------------------------- #

def _validar_no_es_propio(id_usuario_objetivo, actor_id):
    if actor_id is not None and id_usuario_objetivo == actor_id:
        raise AutorizadorError(
            "SELF_ADMIN_NOT_ALLOWED",
            "No puedes administrar tu propio registro de autorizador",
            403,
        )


def _validar_vigencia(inicio, fin):
    if not inicio or not fin:
        raise AutorizadorError(
            "INVALID_VALIDITY", "Las fechas de inicio y fin de vigencia son obligatorias", 400,
            {"fechaFinVigencia": ["Obligatoria"]},
        )
    if fin < inicio:
        raise AutorizadorError(
            "INVALID_VALIDITY", "La fecha de fin no puede ser anterior a la de inicio", 400,
            {"fechaFinVigencia": ["Debe ser igual o posterior a la fecha de inicio"]},
        )


def _normalizar_alcance(alcance: dict, clave: str) -> list[tuple]:
    alcance = alcance or {}
    centros = alcance.get("centros") or []
    tipos_centro = alcance.get("tiposCentro") or []
    if not all(isinstance(c, int) and not isinstance(c, bool) for c in centros):
        raise _validacion({"tipos": [f"{clave}: los centros deben ser identificadores numéricos"]})
    invalidos = [t for t in tipos_centro if t not in TIPOS_CENTRO_VALIDOS]
    if invalidos:
        raise _validacion({"tipos": [f"{clave}: tipo de centro inválido {invalidos}"]})

    claves = []
    if alcance.get("global"):
        claves.append(_clave_alcance(GLOBAL, None, None))
    claves += [_clave_alcance(CENTRO, c, None) for c in dict.fromkeys(centros)]
    claves += [_clave_alcance(TIPO_CENTRO, None, t) for t in dict.fromkeys(tipos_centro)]
    if not claves:
        raise AutorizadorError(
            "SCOPE_REQUIRED",
            f"El tipo {clave} necesita al menos un centro de atención",
            400,
            {"tipos": [f"{clave}: selecciona centros, tipos de centro o alcance global"]},
        )
    return claves


def _normalizar_tipos(tipos: list, *, inicio, fin, puede_otorgar_global: bool) -> list[dict]:
    """Devuelve [{tipo, inicio, fin, alcances:[clave_alcance]}] validado."""
    if not tipos:
        raise _validacion({"tipos": ["Asigna al menos un tipo de autorización"]})
    claves = [t.get("claveTipo") for t in tipos]
    if len(set(claves)) != len(claves):
        raise _validacion({"tipos": ["Un tipo de autorización no puede repetirse"]})

    catalogo = Repo.tipos_por_clave(claves)
    faltantes = [c for c in claves if c not in catalogo]
    if faltantes:
        raise _validacion({"tipos": [f"Tipos de autorización no encontrados: {faltantes}"]})

    normalizados = []
    for item in tipos:
        clave = item["claveTipo"]
        alcances = _normalizar_alcance(item.get("alcance"), clave)
        if any(a[0] == GLOBAL for a in alcances) and not puede_otorgar_global:
            raise AutorizadorError(
                "GLOBAL_PERMISSION_REQUIRED", "No tienes permiso para otorgar alcance GLOBAL", 403,
            )
        tipo_inicio = item.get("fechaInicioVigencia")
        tipo_fin = item.get("fechaFinVigencia")
        if (tipo_inicio and tipo_inicio < inicio) or (tipo_fin and tipo_fin > fin) or (
            tipo_inicio and tipo_fin and tipo_fin < tipo_inicio
        ):
            raise AutorizadorError(
                "INVALID_VALIDITY",
                f"La vigencia del tipo {clave} debe estar dentro de la vigencia del autorizador",
                400,
                {"tipos": [f"{clave}: vigencia fuera del periodo del autorizador"]},
            )
        normalizados.append({
            "tipo": catalogo[clave], "inicio": tipo_inicio, "fin": tipo_fin, "alcances": alcances,
        })

    ids_centro = {a[1] for n in normalizados for a in n["alcances"] if a[0] == CENTRO}
    faltan_centros = sorted(ids_centro - Repo.ids_centros_existentes(ids_centro))
    if faltan_centros:
        raise _validacion({"tipos": [f"Centros de atención no encontrados: {faltan_centros}"]})
    return normalizados


def _validar_cedula(id_usuario, tipos_normalizados):
    if any(n["tipo"].requiere_cedula for n in tipos_normalizados) and not Repo.usuario_tiene_cedula(id_usuario):
        raise AutorizadorError(
            "CEDULA_REQUIRED",
            "El usuario no tiene cédula profesional. Captúrala en Usuarios antes de asignarlo como autorizador.",
            400,
            {"usuarioId": ["Sin cédula profesional registrada en Usuarios"]},
        )


def _validar_motivo(datos, ambito):
    id_motivo = datos.get("motivoId")
    if not id_motivo:
        raise AutorizadorError("REASON_REQUIRED", "Selecciona un motivo", 400, {"motivoId": ["Obligatorio"]})
    motivo = Repo.motivo(id_motivo)
    if motivo is None or motivo.ambito != ambito:
        raise _validacion({"motivoId": [f"Motivo no encontrado para {ambito.lower()}"]})
    descripcion = (datos.get("descripcionMotivo") or "").strip() or None
    if motivo.requiere_descripcion_libre and not descripcion:
        raise AutorizadorError(
            "REASON_REQUIRED", "Describe el motivo", 400, {"descripcionMotivo": ["Obligatoria con este motivo"]},
        )
    return motivo, descripcion


def _bloquear(id_autorizador, datos, actor_id, *, permite_inactivo=False) -> Autorizador:
    """Bloquea la fila y valida existencia, estatus, propiedad y version."""
    autorizador = Repo.obtener_para_actualizar(id_autorizador)
    if autorizador is None:
        raise AutorizadorError("AUTHORIZER_NOT_FOUND", "Autorizador no encontrado", 404)
    if not permite_inactivo and autorizador.estatus == Autorizador.Estatus.INACTIVO:
        raise AutorizadorError(
            "AUTHORIZER_INACTIVE", "El autorizador está dado de baja y no se puede modificar", 409,
        )
    _validar_no_es_propio(autorizador.usuario_id, actor_id)
    if datos.get("version") != autorizador.version:
        raise AutorizadorError(
            "STALE_VERSION",
            "Otro usuario modificó este autorizador. Recarga la información e intenta de nuevo.",
            409,
            {"versionActual": autorizador.version},
        )
    return autorizador


def _marcar_modificado(autorizador, actor_id):
    autorizador.version += 1
    autorizador.fecha_modificacion = timezone.now()
    autorizador.id_usuario_modificacion = actor_id


# ---------------------------------------------------------------------- #
# Escritura de tipos y alcance                                           #
# ---------------------------------------------------------------------- #

def _crear_alcance(autorizador_tipo, clave_alcance, actor_id):
    tipo_alcance, id_centro, tipo_centro = clave_alcance
    return AutorizadorAlcance.objects.create(
        autorizador_tipo=autorizador_tipo,
        tipo_alcance=tipo_alcance,
        centro_atencion_id=id_centro,
        tipo_centro=tipo_centro,
        id_usuario_creacion=actor_id,
    )


def _dar_baja(registro, actor_id, ahora):
    registro.esta_activo = False
    registro.fecha_baja = ahora
    registro.id_usuario_baja = actor_id
    registro.save(update_fields=["esta_activo", "fecha_baja", "id_usuario_baja"])


def _alcance_a_dict(clave_alcance):
    tipo_alcance, id_centro, tipo_centro = clave_alcance
    return {"tipoAlcance": tipo_alcance, "centroId": id_centro, "tipoCentro": tipo_centro}


class AutorizadorUseCase:

    @staticmethod
    def crear(datos: dict, *, actor_id, puede_otorgar_global: bool, auditoria: Auditoria,
              identificador_peticion=None) -> Autorizador:
        id_usuario = datos["usuarioId"]
        _validar_no_es_propio(id_usuario, actor_id)
        inicio, fin = datos.get("fechaInicioVigencia"), datos.get("fechaFinVigencia")
        _validar_vigencia(inicio, fin)
        tipos = _normalizar_tipos(
            datos.get("tipos"), inicio=inicio, fin=fin, puede_otorgar_global=puede_otorgar_global,
        )

        usuario = Repo.usuario(id_usuario)
        if usuario is None or not usuario.est_activo:
            raise AutorizadorError(
                "USER_INVALID", "El usuario no existe o está inactivo", 400,
                {"usuarioId": ["Selecciona un usuario activo"]},
            )
        if Repo.existe_vigente_para_usuario(id_usuario):
            raise AutorizadorError("AUTHORIZER_EXISTS", "El usuario ya está registrado como autorizador", 409)
        _validar_cedula(id_usuario, tipos)

        try:
            with transaction.atomic():
                autorizador = Autorizador.objects.create(
                    usuario_id=id_usuario,
                    cargo=datos.get("cargo") or None,
                    numero_oficio=datos.get("numeroOficio") or None,
                    fecha_inicio_vigencia=inicio,
                    fecha_fin_vigencia=fin,
                    id_usuario_creacion=actor_id,
                )
                for item in tipos:
                    autorizador_tipo = AutorizadorTipo.objects.create(
                        autorizador=autorizador,
                        tipo_autorizacion=item["tipo"],
                        fecha_inicio_vigencia=item["inicio"],
                        fecha_fin_vigencia=item["fin"],
                        id_usuario_creacion=actor_id,
                    )
                    for clave_alcance in item["alcances"]:
                        _crear_alcance(autorizador_tipo, clave_alcance, actor_id)

                despues = snapshot(autorizador)
                Repo.registrar_movimiento(
                    autorizador, "ALTA", id_usuario_responsable=actor_id,
                    datos_nuevos=despues, identificador_peticion=identificador_peticion,
                )
                auditoria("AutorizadorCreado", autorizador.pk, None, despues)
        except IntegrityError as exc:  # carrera con otra alta del mismo usuario
            raise AutorizadorError(
                "AUTHORIZER_EXISTS", "El usuario ya está registrado como autorizador", 409,
            ) from exc
        return autorizador

    @staticmethod
    def actualizar(id_autorizador, datos: dict, *, actor_id, puede_otorgar_global: bool,
                   auditoria: Auditoria, identificador_peticion=None) -> Autorizador:
        with transaction.atomic():
            autorizador = _bloquear(id_autorizador, datos, actor_id)
            antes = snapshot(autorizador)
            if antes["tipos"] and any(t["alcance"]["global"] for t in antes["tipos"]) and not puede_otorgar_global:
                raise AutorizadorError(
                    "GLOBAL_PERMISSION_REQUIRED",
                    "No tienes permiso para modificar un autorizador con alcance GLOBAL",
                    403,
                )
            tipos = _normalizar_tipos(
                datos.get("tipos"),
                inicio=autorizador.fecha_inicio_vigencia,
                fin=autorizador.fecha_fin_vigencia,
                puede_otorgar_global=puede_otorgar_global,
            )
            _validar_cedula(autorizador.usuario_id, tipos)

            def movimiento(tipo_movimiento, anteriores=None, nuevos=None):
                Repo.registrar_movimiento(
                    autorizador, tipo_movimiento, id_usuario_responsable=actor_id,
                    datos_anteriores=anteriores, datos_nuevos=nuevos,
                    identificador_peticion=identificador_peticion,
                )

            # Datos generales
            generales_antes = {"cargo": autorizador.cargo, "numeroOficio": autorizador.numero_oficio}
            if "cargo" in datos:
                autorizador.cargo = datos.get("cargo") or None
            if "numeroOficio" in datos:
                autorizador.numero_oficio = datos.get("numeroOficio") or None
            generales_despues = {"cargo": autorizador.cargo, "numeroOficio": autorizador.numero_oficio}
            if generales_antes != generales_despues:
                movimiento("EDICION", generales_antes, generales_despues)

            # Tipos y alcance: diff con baja logica
            ahora = timezone.now()
            actuales = {t.tipo_autorizacion.clave: t for t in Repo.tipos_activos(autorizador.pk)}
            alcances_actuales = Repo.alcances_activos([t.pk for t in actuales.values()])
            deseados = {item["tipo"].clave: item for item in tipos}

            for clave, autorizador_tipo in actuales.items():
                if clave in deseados:
                    continue
                for alcance in alcances_actuales:
                    if alcance.autorizador_tipo_id == autorizador_tipo.pk:
                        _dar_baja(alcance, actor_id, ahora)
                _dar_baja(autorizador_tipo, actor_id, ahora)
                movimiento("BAJA_TIPO", {"clave": clave}, None)

            for clave, item in deseados.items():
                autorizador_tipo = actuales.get(clave)
                if autorizador_tipo is None:
                    autorizador_tipo = AutorizadorTipo.objects.create(
                        autorizador=autorizador, tipo_autorizacion=item["tipo"],
                        fecha_inicio_vigencia=item["inicio"], fecha_fin_vigencia=item["fin"],
                        id_usuario_creacion=actor_id,
                    )
                    for clave_alcance in item["alcances"]:
                        _crear_alcance(autorizador_tipo, clave_alcance, actor_id)
                    movimiento("ALTA_TIPO", None, {
                        "clave": clave, "alcance": [_alcance_a_dict(a) for a in item["alcances"]],
                    })
                    continue

                if (autorizador_tipo.fecha_inicio_vigencia, autorizador_tipo.fecha_fin_vigencia) != (
                    item["inicio"], item["fin"]
                ):
                    anteriores = {
                        "clave": clave,
                        "fechaInicioVigencia": _iso(autorizador_tipo.fecha_inicio_vigencia),
                        "fechaFinVigencia": _iso(autorizador_tipo.fecha_fin_vigencia),
                    }
                    autorizador_tipo.fecha_inicio_vigencia = item["inicio"]
                    autorizador_tipo.fecha_fin_vigencia = item["fin"]
                    autorizador_tipo.fecha_modificacion = ahora
                    autorizador_tipo.id_usuario_modificacion = actor_id
                    autorizador_tipo.save()
                    movimiento("EDICION", anteriores, {
                        "clave": clave,
                        "fechaInicioVigencia": _iso(item["inicio"]),
                        "fechaFinVigencia": _iso(item["fin"]),
                    })

                existentes = {
                    _clave_alcance(a.tipo_alcance, a.centro_atencion_id, a.tipo_centro): a
                    for a in alcances_actuales if a.autorizador_tipo_id == autorizador_tipo.pk
                }
                deseadas = set(item["alcances"])
                for clave_alcance, alcance in existentes.items():
                    if clave_alcance not in deseadas:
                        _dar_baja(alcance, actor_id, ahora)
                        movimiento("BAJA_CENTRO", {"clave": clave, **_alcance_a_dict(clave_alcance)}, None)
                for clave_alcance in item["alcances"]:
                    if clave_alcance not in existentes:
                        _crear_alcance(autorizador_tipo, clave_alcance, actor_id)
                        movimiento("ALTA_CENTRO", None, {"clave": clave, **_alcance_a_dict(clave_alcance)})

            _marcar_modificado(autorizador, actor_id)
            autorizador.save()
            auditoria("AutorizadorActualizado", autorizador.pk, antes, snapshot(autorizador))
        return autorizador

    @staticmethod
    def suspender(id_autorizador, datos: dict, *, actor_id, auditoria: Auditoria,
                  identificador_peticion=None) -> Autorizador:
        with transaction.atomic():
            autorizador = _bloquear(id_autorizador, datos, actor_id)
            if autorizador.estatus != Autorizador.Estatus.ACTIVO:
                raise AutorizadorError(
                    "INVALID_STATUS_TRANSITION", "Solo se puede suspender un autorizador activo", 409,
                )
            motivo, descripcion = _validar_motivo(datos, Motivo.Ambito.SUSPENSION)
            antes = snapshot(autorizador)
            autorizador.estatus = Autorizador.Estatus.SUSPENDIDO
            autorizador.motivo_estatus = motivo
            autorizador.descripcion_motivo_estatus = descripcion
            autorizador.fecha_fin_suspension = datos.get("fechaFinSuspension")
            _marcar_modificado(autorizador, actor_id)
            autorizador.save()
            despues = snapshot(autorizador)
            Repo.registrar_movimiento(
                autorizador, "SUSPENSION", id_usuario_responsable=actor_id, motivo=motivo,
                descripcion_motivo=descripcion, datos_anteriores=antes, datos_nuevos=despues,
                identificador_peticion=identificador_peticion,
            )
            auditoria("AutorizadorSuspendido", autorizador.pk, antes, despues)
        return autorizador

    @staticmethod
    def reactivar(id_autorizador, datos: dict, *, actor_id, auditoria: Auditoria,
                  identificador_peticion=None) -> Autorizador:
        with transaction.atomic():
            autorizador = _bloquear(id_autorizador, datos, actor_id)
            if autorizador.estatus != Autorizador.Estatus.SUSPENDIDO:
                raise AutorizadorError(
                    "INVALID_STATUS_TRANSITION", "Solo se puede reactivar un autorizador suspendido", 409,
                )
            antes = snapshot(autorizador)
            autorizador.estatus = Autorizador.Estatus.ACTIVO
            autorizador.motivo_estatus = None
            autorizador.descripcion_motivo_estatus = None
            autorizador.fecha_fin_suspension = None
            _marcar_modificado(autorizador, actor_id)
            autorizador.save()
            despues = snapshot(autorizador)
            Repo.registrar_movimiento(
                autorizador, "REACTIVACION", id_usuario_responsable=actor_id,
                datos_anteriores=antes, datos_nuevos=despues, identificador_peticion=identificador_peticion,
            )
            auditoria("AutorizadorReactivado", autorizador.pk, antes, despues)
        return autorizador

    @staticmethod
    def dar_de_baja(id_autorizador, datos: dict, *, actor_id, auditoria: Auditoria,
                    identificador_peticion=None) -> Autorizador:
        with transaction.atomic():
            autorizador = _bloquear(id_autorizador, datos, actor_id)
            motivo, descripcion = _validar_motivo(datos, Motivo.Ambito.BAJA)
            antes = snapshot(autorizador)
            ahora = timezone.now()
            autorizador.estatus = Autorizador.Estatus.INACTIVO
            autorizador.motivo_estatus = motivo
            autorizador.descripcion_motivo_estatus = descripcion
            autorizador.fecha_fin_suspension = None
            autorizador.esta_activo = False
            autorizador.fecha_baja = ahora
            autorizador.id_usuario_baja = actor_id
            _marcar_modificado(autorizador, actor_id)
            autorizador.save()
            despues = snapshot(autorizador)
            Repo.registrar_movimiento(
                autorizador, "BAJA", id_usuario_responsable=actor_id, motivo=motivo,
                descripcion_motivo=descripcion, datos_anteriores=antes, datos_nuevos=despues,
                identificador_peticion=identificador_peticion,
            )
            auditoria("AutorizadorDadoDeBaja", autorizador.pk, antes, despues)
        return autorizador

    @staticmethod
    def renovar(id_autorizador, datos: dict, *, actor_id, auditoria: Auditoria,
                identificador_peticion=None) -> Autorizador:
        with transaction.atomic():
            autorizador = _bloquear(id_autorizador, datos, actor_id)
            nueva_fin = datos.get("fechaFinVigencia")
            if not nueva_fin or nueva_fin <= autorizador.fecha_fin_vigencia:
                raise AutorizadorError(
                    "INVALID_VALIDITY",
                    "La nueva fecha de fin debe ser posterior a la vigencia actual",
                    400,
                    {"fechaFinVigencia": [f"Posterior a {autorizador.fecha_fin_vigencia.isoformat()}"]},
                )
            anteriores = {"fechaFinVigencia": _iso(autorizador.fecha_fin_vigencia)}
            antes = snapshot(autorizador)
            autorizador.fecha_fin_vigencia = nueva_fin
            _marcar_modificado(autorizador, actor_id)
            autorizador.save()
            Repo.registrar_movimiento(
                autorizador, "RENOVACION", id_usuario_responsable=actor_id,
                datos_anteriores=anteriores, datos_nuevos={"fechaFinVigencia": _iso(nueva_fin)},
                identificador_peticion=identificador_peticion,
            )
            auditoria("AutorizadorRenovado", autorizador.pk, antes, snapshot(autorizador))
        return autorizador
