"""Motor de solicitudes de autorizacion (plan autorizadores-medicos, reglas S1-S7 y D1-D8).

Decisiones confirmadas (2026-10-27): PRIMERO_VALIDO por defecto en los 4 tipos
(configurable por centro), en MULTIPLE un rechazo resuelve la solicitud y una
solicitud pendiente vence a las 72 horas.

Concurrencia: decidir bloquea la fila (SELECT ... FOR UPDATE) y revalida todo
dentro de la transaccion. Una decision por autorizador y contenido (UNIQUE en
BD). La `version` evita decidir sobre una pantalla desactualizada.
"""
from __future__ import annotations

import hashlib
import json
import uuid as uuid_lib
from datetime import timedelta
from typing import Callable

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.authentication.services.errors import AuthServiceError
from apps.authentication.services.firma.verificador import VerificadorSimple

from .. import events
from ..contracts import autorizadores_elegibles, puede_autorizar
from ..models import (
    Modalidad,
    Motivo,
    Solicitud,
    SolicitudDecision,
    SolicitudDestinatario,
    SolicitudItem,
    SolicitudTransicion,
)
from ..repositories.solicitud_repository import SolicitudRepository as Repo

Auditoria = Callable[..., None]
PENDIENTE = Solicitud.Estatus.PENDIENTE


class SolicitudError(Exception):
    def __init__(self, code: str, message: str, http_status: int, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _validacion(details):
    return SolicitudError("VALIDATION_ERROR", "Datos de entrada inválidos", 400, details)


def _hash_contenido(clave_tipo, tipo_origen, id_origen, id_centro, items, motivos) -> str:
    canonico = json.dumps(
        {
            "tipo": clave_tipo,
            "origen": [tipo_origen, id_origen],
            "centro": id_centro,
            "items": sorted(
                [
                    [i["tipoItem"], i["idItemOrigen"], i["descripcion"], str(i.get("cantidad")), i.get("motivo")]
                    for i in items
                ],
                key=lambda fila: (fila[0], fila[1]),
            ),
            "motivos": sorted(motivos),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def snapshot(solicitud: Solicitud) -> dict:
    return {
        "id": solicitud.pk,
        "folio": solicitud.folio,
        "estatus": solicitud.estatus,
        "tipoOrigen": solicitud.tipo_origen,
        "idOrigen": solicitud.id_origen,
        "centroId": solicitud.centro_atencion_id,
        "modalidad": solicitud.modalidad,
        "aprobacionesRequeridas": solicitud.aprobaciones_requeridas,
        "hashContenido": solicitud.hash_contenido,
        "version": solicitud.version,
        "idUsuarioResolucion": solicitud.id_usuario_resolucion,
        "motivoCierreId": solicitud.motivo_cierre_id,
    }


def _transicion(solicitud, anterior, evento, id_usuario=None, detalle=None):
    SolicitudTransicion.objects.create(
        solicitud=solicitud, estatus_anterior=anterior, estatus_nuevo=solicitud.estatus,
        evento=evento, id_usuario=id_usuario, detalle=detalle,
    )


def _crear_items(solicitud, items):
    for item in items:
        SolicitudItem.objects.create(
            solicitud=solicitud,
            tipo_item=item["tipoItem"],
            id_item_origen=item["idItemOrigen"],
            descripcion=item["descripcion"][:255],
            cantidad=item.get("cantidad"),
            motivo=item.get("motivo"),
            requiere_autorizacion=item.get("requiereAutorizacion", True),
        )


def _evento_resuelta(solicitud) -> events.SolicitudResuelta:
    return events.SolicitudResuelta(
        id_solicitud=solicitud.pk,
        uuid_publico=str(solicitud.uuid_publico),
        folio=solicitud.folio,
        clave_tipo=solicitud.tipo_autorizacion.clave,
        tipo_origen=solicitud.tipo_origen,
        id_origen=solicitud.id_origen,
        estatus=solicitud.estatus,
        id_usuario_resolucion=solicitud.id_usuario_resolucion,
        clave_motivo=solicitud.motivo_cierre.clave if solicitud.motivo_cierre_id else None,
        texto_motivo=(
            " — ".join(filter(None, [solicitud.motivo_cierre.descripcion, solicitud.descripcion_motivo_cierre]))
            if solicitud.motivo_cierre_id
            else None
        ),
    )


def _cerrar_destinatarios_pendientes(solicitud):
    SolicitudDestinatario.objects.filter(
        solicitud=solicitud,
        estatus__in=[SolicitudDestinatario.Estatus.NOTIFICADO, SolicitudDestinatario.Estatus.VISTO],
    ).update(estatus=SolicitudDestinatario.Estatus.ATENDIDA_POR_OTRO)


def acciones_para(solicitud: Solicitud, id_usuario: int) -> dict:
    """Lo que el usuario puede hacer HOY con la solicitud (para la pantalla).
    Al decidir se vuelve a validar todo dentro de la transaccion."""
    def bloqueo(codigo, mensaje):
        return {"puedeAprobar": False, "puedeRechazar": False, "motivoBloqueo": codigo, "mensajeBloqueo": mensaje}

    if solicitud.estatus != PENDIENTE:
        return bloqueo("SOLICITUD_RESUELTA", "Esta solicitud ya no está pendiente.")
    decision = puede_autorizar(
        id_usuario, solicitud.tipo_autorizacion.clave, solicitud.centro_atencion_id,
        id_usuario_solicitante=solicitud.id_usuario_solicitante,
    )
    if not decision:
        return bloqueo(decision.motivo.value, decision.mensaje)
    if Repo.ya_decidio(solicitud, decision.id_autorizador):
        return bloqueo("YA_DECIDIO", "Ya registraste tu decisión sobre esta solicitud.")
    return {
        "puedeAprobar": True,
        "puedeRechazar": solicitud.tipo_autorizacion.permite_rechazo,
        "motivoBloqueo": None,
        "mensajeBloqueo": None,
    }


class SolicitudUseCase:

    @staticmethod
    def solicitar(*, clave_tipo, id_origen, id_centro, id_usuario_solicitante, items, motivos,
                  folio_origen=None, resumen_minimo=None, id_paciente=None,
                  prioridad=Solicitud.Prioridad.NORMAL) -> Solicitud:
        tipo = Repo.tipo_por_clave(clave_tipo)
        if tipo is None:
            raise _validacion({"claveTipo": [f"Tipo de autorización no encontrado: {clave_tipo}"]})
        if not items:
            raise _validacion({"items": ["La solicitud necesita al menos un elemento a autorizar"]})
        centro = Repo.centro(id_centro)
        if centro is None:
            raise _validacion({"centroId": ["Centro de atención no encontrado"]})

        motivos = list(dict.fromkeys(motivos or []))
        hash_contenido = _hash_contenido(clave_tipo, tipo.tipo_origen, id_origen, id_centro, items, motivos)

        with transaction.atomic():
            existente = Repo.pendiente_por_origen_para_actualizar(tipo.tipo_origen, id_origen)
            if existente is not None:
                if existente.hash_contenido == hash_contenido:
                    return existente
                # El documento cambio: nuevo contenido, las aprobaciones previas dejan de contar.
                SolicitudItem.objects.filter(solicitud=existente, esta_activo=True).update(esta_activo=False)
                _crear_items(existente, items)
                detalle = {"hashAnterior": existente.hash_contenido, "hashNuevo": hash_contenido}
                existente.hash_contenido = hash_contenido
                existente.motivos = motivos
                existente.resumen_minimo = resumen_minimo or {}
                existente.version += 1
                existente.fecha_modificacion = timezone.now()
                existente.id_usuario_modificacion = id_usuario_solicitante
                existente.save()
                _transicion(existente, PENDIENTE, "RECALCULADA", id_usuario_solicitante, detalle)
                return existente

            regla = Repo.regla_centro(tipo, id_centro)
            modalidad = (regla and regla.modalidad) or tipo.modalidad_predeterminada
            aprobaciones = (regla and regla.aprobaciones_requeridas) or tipo.aprobaciones_requeridas
            horas = (regla and regla.horas_vigencia_solicitud) or tipo.horas_vigencia_solicitud
            if modalidad == Modalidad.PRIMERO_VALIDO:
                aprobaciones = 1

            ahora = timezone.now()
            solicitud = Solicitud.objects.create(
                folio=uuid_lib.uuid4().hex,  # provisional: el folio sale del id
                tipo_autorizacion=tipo,
                tipo_origen=tipo.tipo_origen,
                id_origen=id_origen,
                folio_origen=folio_origen,
                centro_atencion=centro,
                clues=centro.code,
                paciente_id=id_paciente,
                id_usuario_solicitante=id_usuario_solicitante,
                motivos=motivos,
                modalidad=modalidad,
                aprobaciones_requeridas=aprobaciones,
                prioridad=prioridad,
                fecha_limite=ahora + timedelta(hours=horas),
                resumen_minimo=resumen_minimo or {},
                hash_contenido=hash_contenido,
                id_usuario_creacion=id_usuario_solicitante,
            )
            solicitud.folio = f"AUT-{timezone.localtime(ahora).year}-{solicitud.pk:06d}"
            _crear_items(solicitud, items)

            elegibles = autorizadores_elegibles(clave_tipo, id_centro, excluir_id_usuario=id_usuario_solicitante)
            for elegible in elegibles:
                SolicitudDestinatario.objects.create(
                    solicitud=solicitud, autorizador_id=elegible.id_autorizador,
                    tipo_seleccion=SolicitudDestinatario.TipoSeleccion.ELEGIBLES,
                )
            solicitud.sin_elegibles = not elegibles
            solicitud.save(update_fields=["folio", "sin_elegibles"])
            _transicion(solicitud, None, "CREADA", id_usuario_solicitante, {"destinatarios": len(elegibles)})
            events.publicar(events.SolicitudCreada(
                id_solicitud=solicitud.pk,
                uuid_publico=str(solicitud.uuid_publico),
                folio=solicitud.folio,
                ids_autorizador_destinatarios=tuple(e.id_autorizador for e in elegibles),
            ))
        return solicitud

    @staticmethod
    def decidir(uuid_publico, datos: dict, *, actor, auditoria: Auditoria, ip=None, agente_usuario=None,
                identificador_peticion=None) -> Solicitud:
        decision = datos.get("decision")
        if decision not in SolicitudDecision.Decision.values:
            raise _validacion({"decision": ["Debe ser APROBAR o RECHAZAR"]})

        with transaction.atomic():
            solicitud = Repo.para_actualizar(uuid_publico)
            if solicitud is None:
                raise SolicitudError("REQUEST_NOT_FOUND", "Solicitud no encontrada", 404)
            if solicitud.estatus != PENDIENTE:
                raise SolicitudError(
                    "ALREADY_RESOLVED", f"La solicitud ya está {solicitud.get_estatus_display().lower()}.", 409,
                    {"estatus": solicitud.estatus},
                )
            if datos.get("version") != solicitud.version:
                raise SolicitudError(
                    "STALE_VERSION", "La solicitud cambió mientras la revisabas. Recarga e intenta de nuevo.", 409,
                    {"versionActual": solicitud.version},
                )

            tipo = solicitud.tipo_autorizacion
            politica = puede_autorizar(
                actor.id_usuario, tipo.clave, solicitud.centro_atencion_id,
                id_usuario_solicitante=solicitud.id_usuario_solicitante,
            )
            if not politica:
                raise SolicitudError("NOT_AUTHORIZED", politica.mensaje, 403, {"motivo": politica.motivo.value})

            motivo, descripcion = None, (datos.get("descripcionMotivo") or "").strip() or None
            if decision == SolicitudDecision.Decision.RECHAZAR:
                if not tipo.permite_rechazo:
                    raise SolicitudError("REJECTION_NOT_ALLOWED", "Este tipo de autorización no admite rechazo.", 409)
                motivo = Motivo.objects.filter(
                    pk=datos.get("motivoId") or 0, ambito=Motivo.Ambito.RECHAZO, esta_activo=True,
                ).first()
                if motivo is None:
                    raise SolicitudError("REASON_REQUIRED", "Selecciona el motivo del rechazo.", 400,
                                         {"motivoId": ["Obligatorio al rechazar"]})
                if motivo.requiere_descripcion_libre and not descripcion:
                    raise SolicitudError("REASON_REQUIRED", "Describe el motivo del rechazo.", 400,
                                         {"descripcionMotivo": ["Obligatoria con este motivo"]})

            if Repo.ya_decidio(solicitud, politica.id_autorizador):
                raise SolicitudError("DUPLICATE_DECISION", "Ya registraste tu decisión sobre esta solicitud.", 409)

            if tipo.metodo_firma_minimo != VerificadorSimple.metodo:
                raise SolicitudError(
                    "SIGNATURE_METHOD_NOT_AVAILABLE",
                    "Este tipo de autorización exige un método de firma que aún no está disponible.", 409,
                )
            try:
                firma = VerificadorSimple().verificar(actor, datos.get("credencial"), solicitud.hash_contenido)
            except AuthServiceError as exc:
                raise SolicitudError(exc.code, exc.message, exc.status_code, exc.details) from exc

            antes = snapshot(solicitud)
            try:
                SolicitudDecision.objects.create(
                    solicitud=solicitud,
                    autorizador_id=politica.id_autorizador,
                    usuario=actor,
                    autorizador_tipo_id=politica.id_autorizador_tipo,
                    alcance_aplicado=politica.alcance_aplicado,
                    numero_cedula=politica.numero_cedula,
                    decision=decision,
                    motivo=motivo,
                    descripcion_motivo=descripcion,
                    metodo_firma=firma.metodo,
                    # El contenido firmado es el de la solicitud (VerificadorSimple
                    # devuelve sha256 de lo que recibe, que ya es ese hash).
                    hash_contenido=solicitud.hash_contenido,
                    fecha_firma=firma.firmado_en,
                    ip_origen=ip,
                    agente_usuario=(agente_usuario or "")[:255] or None,
                    identificador_peticion=identificador_peticion,
                )
            except IntegrityError as exc:
                raise SolicitudError("DUPLICATE_DECISION", "Ya registraste tu decisión sobre esta solicitud.", 409) from exc

            destinatario, _ = SolicitudDestinatario.objects.get_or_create(
                solicitud=solicitud, autorizador_id=politica.id_autorizador,
                defaults={"tipo_seleccion": SolicitudDestinatario.TipoSeleccion.DIRECTO},
            )
            destinatario.estatus = SolicitudDestinatario.Estatus.DECIDIO
            destinatario.save(update_fields=["estatus"])

            # Resolucion segun la modalidad congelada al crear la solicitud.
            if decision == SolicitudDecision.Decision.RECHAZAR:
                if solicitud.modalidad == Modalidad.PRIMERO_VALIDO or tipo.rechazo_resuelve_solicitud:
                    solicitud.estatus = Solicitud.Estatus.RECHAZADA
                    solicitud.motivo_cierre = motivo
                    solicitud.descripcion_motivo_cierre = descripcion
                    evento, accion = "RECHAZADA", "SolicitudRechazada"
                else:
                    evento, accion = "RECHAZO_PARCIAL", "SolicitudRechazoParcial"
            else:
                aprobaron = Repo.ids_aprobaron_contenido_vigente(solicitud)
                completa = len(aprobaron) >= solicitud.aprobaciones_requeridas
                obligatorios_ok = Repo.ids_obligatorios(solicitud) <= aprobaron
                if completa and obligatorios_ok:
                    solicitud.estatus = Solicitud.Estatus.AUTORIZADA
                    evento, accion = "AUTORIZADA", "SolicitudAutorizada"
                else:
                    evento, accion = "APROBACION_PARCIAL", "SolicitudAprobacionParcial"

            resuelta = solicitud.estatus != PENDIENTE
            ahora = timezone.now()
            if resuelta:
                solicitud.id_usuario_resolucion = actor.id_usuario
                solicitud.fecha_resolucion = ahora
                _cerrar_destinatarios_pendientes(solicitud)
            solicitud.version += 1
            solicitud.fecha_modificacion = ahora
            solicitud.id_usuario_modificacion = actor.id_usuario
            solicitud.save()
            _transicion(solicitud, PENDIENTE, evento, actor.id_usuario, {"decision": decision})
            auditoria(accion, solicitud.pk, antes, snapshot(solicitud))
            if resuelta:
                events.publicar(_evento_resuelta(solicitud))
        return solicitud

    @staticmethod
    def vencer_pendientes(ahora=None) -> int:
        """Pasa a VENCIDA las pendientes con fecha limite cumplida. Idempotente."""
        ahora = ahora or timezone.now()
        vencidas = 0
        for id_solicitud in Repo.ids_pendientes_vencidas(ahora):
            with transaction.atomic():
                solicitud = (
                    Solicitud.objects.select_for_update(of=("self",))
                    .select_related("tipo_autorizacion")
                    .filter(pk=id_solicitud, estatus=PENDIENTE, fecha_limite__lt=ahora)
                    .first()
                )
                if solicitud is None:  # la resolvieron mientras tanto
                    continue
                solicitud.estatus = Solicitud.Estatus.VENCIDA
                solicitud.version += 1
                solicitud.fecha_modificacion = ahora
                solicitud.save()
                _transicion(solicitud, PENDIENTE, "VENCIDA")
                events.publicar(_evento_resuelta(solicitud))
                vencidas += 1
        return vencidas

    @staticmethod
    def escalar_pendientes(ahora=None) -> int:
        """F7: pendientes sin respuesta tras las horas de su tipo (24 por defecto).
        Recuerda a los destinatarios que hoy pueden autorizar y suma a los elegibles
        que faltaban; si no queda nadie, avisa al solicitante. Una vez por solicitud.
        No sube la version: no cambia lo que se autoriza."""
        ahora = ahora or timezone.now()
        escaladas = 0
        for id_solicitud in Repo.ids_por_escalar(ahora):
            with transaction.atomic():
                solicitud = (
                    Solicitud.objects.select_for_update(of=("self",))
                    .select_related("tipo_autorizacion")
                    .filter(pk=id_solicitud, estatus=PENDIENTE, fecha_escalamiento__isnull=True)
                    .first()
                )
                if solicitud is None:  # resuelta o escalada mientras tanto
                    continue
                elegibles = {
                    e.id_autorizador
                    for e in autorizadores_elegibles(
                        solicitud.tipo_autorizacion.clave, solicitud.centro_atencion_id,
                        excluir_id_usuario=solicitud.id_usuario_solicitante,
                    )
                }
                actuales = dict(
                    SolicitudDestinatario.objects.filter(solicitud=solicitud)
                    .values_list("autorizador_id", "estatus")
                )
                esperando = (SolicitudDestinatario.Estatus.NOTIFICADO, SolicitudDestinatario.Estatus.VISTO)
                recordatorio = sorted(a for a, estatus in actuales.items() if estatus in esperando and a in elegibles)
                nuevos = sorted(elegibles - set(actuales))
                for id_autorizador in nuevos:
                    SolicitudDestinatario.objects.create(
                        solicitud=solicitud, autorizador_id=id_autorizador,
                        tipo_seleccion=SolicitudDestinatario.TipoSeleccion.ESCALAMIENTO,
                    )
                sin_elegibles = not recordatorio and not nuevos
                solicitud.fecha_escalamiento = ahora
                solicitud.sin_elegibles = sin_elegibles
                solicitud.save(update_fields=["fecha_escalamiento", "sin_elegibles"])
                _transicion(solicitud, PENDIENTE, "ESCALADA", None,
                            {"recordatorio": recordatorio, "nuevos": nuevos})
                events.publicar(events.SolicitudEscalada(
                    id_solicitud=solicitud.pk, ids_autorizador_recordatorio=tuple(recordatorio),
                    ids_autorizador_nuevos=tuple(nuevos), sin_elegibles=sin_elegibles,
                ))
                escaladas += 1
        return escaladas

    @staticmethod
    def cancelar_por_origen(tipo_origen, id_origen, *, id_usuario) -> bool:
        """El documento de origen se cancelo: su solicitud pendiente se cancela."""
        with transaction.atomic():
            solicitud = Repo.pendiente_por_origen_para_actualizar(tipo_origen, id_origen)
            if solicitud is None:
                return False
            solicitud.estatus = Solicitud.Estatus.CANCELADA
            solicitud.motivo_cierre = Motivo.objects.filter(
                ambito=Motivo.Ambito.CANCELACION, clave="ORIGEN_CANCELADO",
            ).first()
            solicitud.version += 1
            solicitud.fecha_modificacion = timezone.now()
            solicitud.id_usuario_modificacion = id_usuario
            solicitud.save()
            _cerrar_destinatarios_pendientes(solicitud)
            _transicion(solicitud, PENDIENTE, "CANCELADA_ORIGEN", id_usuario)
            events.publicar(_evento_resuelta(solicitud))
        return True

    @staticmethod
    def elegibles(uuid_publico, *, actor) -> tuple[Solicitud, list]:
        solicitud = Repo.obtener(uuid_publico)
        if solicitud is None or not Repo.es_visible(solicitud, actor.id_usuario):
            raise SolicitudError("REQUEST_NOT_FOUND", "Solicitud no encontrada", 404)
        return solicitud, autorizadores_elegibles(
            solicitud.tipo_autorizacion.clave, solicitud.centro_atencion_id,
            excluir_id_usuario=solicitud.id_usuario_solicitante,
        )

    @staticmethod
    def notificar(uuid_publico, datos: dict, *, actor, auditoria: Auditoria) -> list[int]:
        """Envio manual: a autorizadores elegidos o a todos los elegibles.
        Solo a quien hoy puede autorizar ese tipo en ese centro."""
        with transaction.atomic():
            solicitud = Repo.para_actualizar(uuid_publico)
            if solicitud is None or not Repo.es_visible(solicitud, actor.id_usuario):
                raise SolicitudError("REQUEST_NOT_FOUND", "Solicitud no encontrada", 404)
            if solicitud.estatus != PENDIENTE:
                raise SolicitudError(
                    "ALREADY_RESOLVED", "Solo se pueden enviar solicitudes pendientes.", 409,
                    {"estatus": solicitud.estatus},
                )
            elegibles = {
                e.id_autorizador
                for e in autorizadores_elegibles(
                    solicitud.tipo_autorizacion.clave, solicitud.centro_atencion_id,
                    excluir_id_usuario=solicitud.id_usuario_solicitante,
                )
            }
            if datos.get("todosElegibles"):
                objetivo = elegibles
            else:
                objetivo = set(datos.get("autorizadorIds") or [])
                if not objetivo:
                    raise _validacion({"autorizadorIds": ["Elige al menos un autorizador o todos los elegibles"]})
                no_elegibles = sorted(objetivo - elegibles)
                if no_elegibles:
                    raise SolicitudError(
                        "RECIPIENT_NOT_ELIGIBLE",
                        "Algunos autorizadores no pueden autorizar este tipo en este centro.",
                        422,
                        {"autorizadorIds": no_elegibles},
                    )
            if not objetivo:
                raise SolicitudError("NO_ELIGIBLE_AUTHORIZERS", "No hay autorizadores elegibles para esta solicitud.", 409)

            for id_autorizador in sorted(objetivo):
                SolicitudDestinatario.objects.get_or_create(
                    solicitud=solicitud, autorizador_id=id_autorizador,
                    defaults={
                        "tipo_seleccion": SolicitudDestinatario.TipoSeleccion.MANUAL,
                        "id_usuario_envio": actor.id_usuario,
                    },
                )
            if solicitud.sin_elegibles:
                solicitud.sin_elegibles = False
                solicitud.save(update_fields=["sin_elegibles"])
            enviados = sorted(objetivo)
            _transicion(solicitud, PENDIENTE, "NOTIFICADA", actor.id_usuario, {"autorizadores": enviados})
            auditoria("SolicitudNotificada", solicitud.pk, None, {"autorizadores": enviados})
            events.publicar(events.SolicitudEnviada(
                id_solicitud=solicitud.pk, ids_autorizador=tuple(enviados), id_usuario_envio=actor.id_usuario,
            ))
        return enviados

    @staticmethod
    def marcar_vista(solicitud, id_usuario):
        autorizador = Repo.autorizador_vigente(id_usuario)
        if autorizador is None:
            return
        SolicitudDestinatario.objects.filter(
            solicitud=solicitud, autorizador=autorizador, estatus=SolicitudDestinatario.Estatus.NOTIFICADO,
        ).update(estatus=SolicitudDestinatario.Estatus.VISTO, fecha_visto=timezone.now())
