import type { ListResponse, PaginationParams } from "@api/types/common.types";
import type { ClaveTipoAutorizacion } from "@api/types/autorizaciones/autorizadores.types";

/**
 * Solicitudes de autorizacion - contrato alineado al backend (apps/autorizaciones):
 * - GET  /autorizaciones/solicitudes/                 bandeja (lo que el usuario puede gestionar)
 * - GET  /autorizaciones/solicitudes/:uuid/           detalle (destino del boton; no cambia el estado)
 * - POST /autorizaciones/solicitudes/:uuid/decision/  aprobar o rechazar (contraseña obligatoria)
 * - GET  /autorizaciones/solicitudes/:uuid/elegibles/ autorizadores que pueden recibirla
 * - POST /autorizaciones/solicitudes/:uuid/notificar/ envio manual
 * - GET  /autorizaciones/motivos-rechazo/
 *
 * Nunca trae la identidad del paciente.
 * Errores (code): NOT_AUTHORIZED, REAUTH_FAILED (403); REAUTH_LOCKED (423);
 * REQUEST_NOT_FOUND (404); ALREADY_RESOLVED, STALE_VERSION, DUPLICATE_DECISION,
 * REJECTION_NOT_ALLOWED (409); REASON_REQUIRED, VALIDATION_ERROR (400);
 * RECIPIENT_NOT_ELIGIBLE (422).
 */

export type EstatusSolicitud = "PENDIENTE" | "AUTORIZADA" | "RECHAZADA" | "VENCIDA" | "CANCELADA";
export type DecisionSolicitud = "APROBAR" | "RECHAZAR";

export interface ReferenciaPersona {
  id: number;
  name: string;
}

export interface AccionesSolicitud {
  puedeAprobar: boolean;
  puedeRechazar: boolean;
  /** Codigo del motivo (p. ej. AUTORIZADOR_SUSPENDIDO, YA_DECIDIO, SOLICITUD_RESUELTA). */
  motivoBloqueo: string | null;
  mensajeBloqueo: string | null;
}

export interface SolicitudResumen {
  uuid: string;
  folio: string;
  tipo: { clave: ClaveTipoAutorizacion; nombre: string };
  centro: { id: number; nombre: string; clues: string };
  tipoOrigen: string;
  folioOrigen: string | null;
  motivos: string[];
  estatus: EstatusSolicitud;
  prioridad: "NORMAL" | "URGENTE";
  modalidad: "PRIMERO_VALIDO" | "MULTIPLE";
  aprobacionesRequeridas: number;
  aprobacionesVigentes: number;
  sinElegibles: boolean;
  resumen: Record<string, unknown>;
  solicitadaPor: ReferenciaPersona | null;
  fechaCreacion: string;
  fechaLimite: string;
  resueltaPor: ReferenciaPersona | null;
  fechaResolucion: string | null;
  motivoCierre: { clave: string; descripcion: string } | null;
  descripcionMotivoCierre: string | null;
  version: number;
}

export interface SolicitudDetalle extends SolicitudResumen {
  items: { tipoItem: string; descripcion: string; cantidad: number | null; motivo: string | null }[];
  destinatarios: {
    autorizador: { id: number; nombre: string };
    estatus: string;
    esObligatorio: boolean;
    tipoSeleccion: string;
  }[];
  decisiones: {
    autorizador: { id: number; nombre: string };
    decision: DecisionSolicitud;
    motivo: { clave: string; descripcion: string } | null;
    descripcionMotivo: string | null;
    fechaFirma: string;
    /** false si el documento cambio despues de firmar (ya no cuenta). */
    vigente: boolean;
  }[];
  acciones: AccionesSolicitud;
}

export interface AutorizadorElegible {
  idAutorizador: number;
  nombre: string;
  alcanceAplicado: string;
  yaNotificado: boolean;
}

export interface MotivoRechazo {
  id: number;
  clave: string;
  descripcion: string;
  requiereDescripcionLibre: boolean;
}

// =============================================================================
// REQUESTS / RESPONSES
// =============================================================================

export interface SolicitudesListParams extends PaginationParams {
  estatus?: EstatusSolicitud;
  tipo?: ClaveTipoAutorizacion;
  centroId?: number;
  folio?: string;
  desde?: string;
  hasta?: string;
}

export interface DecisionRequest {
  decision: DecisionSolicitud;
  motivoId: number | null;
  descripcionMotivo: string | null;
  version: number;
  /** Contraseña propia: firma la decision. */
  credencial: string;
}

export interface NotificarRequest {
  autorizadorIds?: number[];
  todosElegibles?: boolean;
}

export type SolicitudesListResponse = ListResponse<SolicitudResumen>;

export interface SolicitudDetalleResponse {
  solicitud: SolicitudDetalle;
}

export interface NotificarResponse extends SolicitudDetalleResponse {
  notificados: number;
}

export interface ElegiblesResponse {
  items: AutorizadorElegible[];
}

export interface MotivosRechazoResponse {
  items: MotivoRechazo[];
}
