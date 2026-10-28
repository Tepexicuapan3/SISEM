"""Auditoria de solicitudes de autorizacion (trazabilidad NOM-024), solo lectura.

Minima exposicion clinica (decision de la usuaria, 2026-10-28): se muestra folio,
tipo, centro, conteos y el hash firmado; nunca los conceptos autorizados
(medicamentos o estudios) ni datos del paciente. El detalle clinico vive en la
bandeja, con su propio permiso.
"""
from __future__ import annotations

from ..repositories.auditoria_repository import AuditoriaRepository as Repo

MAXIMO_EXPORTACION = 5000


def _fila(solicitud, nombres) -> dict:
    return {
        "uuid": str(solicitud.uuid_publico),
        "folio": solicitud.folio,
        "folioOrigen": solicitud.folio_origen,
        "tipoOrigen": solicitud.tipo_origen,
        "claveTipo": solicitud.tipo_autorizacion.clave,
        "tipoNombre": solicitud.tipo_autorizacion.nombre,
        "centroNombre": solicitud.centro_atencion.name,
        "clues": solicitud.clues,
        "estatus": solicitud.estatus,
        "modalidad": solicitud.modalidad,
        "aprobacionesRequeridas": solicitud.aprobaciones_requeridas,
        "aprobaciones": getattr(solicitud, "total_aprobaciones", None),
        "totalItems": getattr(solicitud, "total_items", None),
        "solicitanteNombre": nombres.get(solicitud.id_usuario_solicitante),
        "fechaCreacion": solicitud.fecha_creacion,
        "fechaLimite": solicitud.fecha_limite,
        "fechaEscalamiento": solicitud.fecha_escalamiento,
        "fechaResolucion": solicitud.fecha_resolucion,
        "resolvioNombre": nombres.get(solicitud.id_usuario_resolucion),
        "motivoCierre": solicitud.motivo_cierre.descripcion if solicitud.motivo_cierre_id else None,
    }


def _nombres_de(solicitudes) -> dict[int, str]:
    return Repo.nombres(
        [s.id_usuario_solicitante for s in solicitudes] + [s.id_usuario_resolucion for s in solicitudes]
    )


class AuditoriaUseCase:
    @staticmethod
    def consulta(filtros: dict):
        return Repo.solicitudes(
            fecha_desde=filtros.get("fechaDesde"),
            fecha_hasta=filtros.get("fechaHasta"),
            clave_tipo=filtros.get("tipo"),
            id_centro=filtros.get("centroId"),
            estatus=filtros.get("estatus"),
            id_autorizador=filtros.get("autorizadorId"),
        )

    @staticmethod
    def filas(solicitudes) -> list[dict]:
        solicitudes = list(solicitudes)
        nombres = _nombres_de(solicitudes)
        return [_fila(s, nombres) for s in solicitudes]

    @staticmethod
    def listar(filtros: dict, limite: int | None = None) -> list[dict]:
        consulta = AuditoriaUseCase.consulta(filtros)
        return AuditoriaUseCase.filas(consulta[:limite] if limite else consulta)

    @staticmethod
    def linea_de_tiempo(uuid_publico) -> dict | None:
        solicitud = Repo.solicitud(uuid_publico)
        if solicitud is None:
            return None
        transiciones = Repo.transiciones(solicitud)
        decisiones = Repo.decisiones(solicitud)
        destinatarios = Repo.destinatarios(solicitud)
        nombres = Repo.nombres(
            [solicitud.id_usuario_solicitante, solicitud.id_usuario_resolucion]
            + [t.id_usuario for t in transiciones]
            + [d.usuario_id for d in decisiones]
            + [d.autorizador.usuario_id for d in destinatarios]
        )
        resumen = _fila(solicitud, nombres)
        resumen["hashContenido"] = solicitud.hash_contenido
        return {
            "solicitud": resumen,
            "eventos": [
                {
                    "fecha": t.fecha_evento,
                    "evento": t.evento,
                    "estatusAnterior": t.estatus_anterior,
                    "estatusNuevo": t.estatus_nuevo,
                    # NULL = proceso automatico (vencimiento, escalamiento).
                    "usuarioNombre": nombres.get(t.id_usuario) if t.id_usuario else None,
                    "detalle": t.detalle,
                }
                for t in transiciones
            ],
            "decisiones": [
                {
                    "fechaFirma": d.fecha_firma,
                    "autorizadorNombre": nombres.get(d.usuario_id),
                    "numeroCedula": d.numero_cedula,
                    "decision": d.decision,
                    "motivo": d.motivo.descripcion if d.motivo_id else None,
                    "descripcionMotivo": d.descripcion_motivo,
                    "alcanceAplicado": d.alcance_aplicado,
                    "metodoFirma": d.metodo_firma,
                    "hashContenido": d.hash_contenido,
                    # Firmo el contenido vigente (un recalculo invalida las firmas anteriores).
                    "firmaVigente": d.hash_contenido == solicitud.hash_contenido,
                    "ipOrigen": d.ip_origen,
                    "agenteUsuario": d.agente_usuario,
                    "identificadorPeticion": d.identificador_peticion,
                }
                for d in decisiones
            ],
            "destinatarios": [
                {
                    "autorizadorNombre": nombres.get(d.autorizador.usuario_id),
                    "tipoSeleccion": d.tipo_seleccion,
                    "estatus": d.estatus,
                    "fechaEnvio": d.fecha_envio,
                    "fechaVisto": d.fecha_visto,
                }
                for d in destinatarios
            ],
        }
