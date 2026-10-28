import type { ListResponse, PaginationParams } from "@api/types/common.types";
import type { EstatusSolicitud } from "@api/types/autorizaciones/solicitudes.types";

/**
 * Auditoria de solicitudes (/autorizaciones/auditoria/solicitudes/), solo lectura.
 * Sin datos clinicos: nunca trae conceptos autorizados ni identidad del paciente.
 */

export interface AuditoriaParams extends PaginationParams {
  fechaDesde?: string;
  fechaHasta?: string;
  tipo?: string;
  centroId?: number;
  estatus?: EstatusSolicitud;
  autorizadorId?: number;
}

export interface AuditoriaFila {
  uuid: string;
  folio: string;
  folioOrigen: string | null;
  tipoOrigen: string;
  claveTipo: string;
  tipoNombre: string;
  centroNombre: string;
  clues: string;
  estatus: EstatusSolicitud;
  modalidad: string;
  aprobacionesRequeridas: number;
  aprobaciones: number | null;
  totalItems: number | null;
  solicitanteNombre: string | null;
  fechaCreacion: string;
  fechaLimite: string;
  fechaEscalamiento: string | null;
  fechaResolucion: string | null;
  resolvioNombre: string | null;
  motivoCierre: string | null;
}

export type AuditoriaListResponse = ListResponse<AuditoriaFila>;

export interface AuditoriaEvento {
  fecha: string;
  evento: string;
  estatusAnterior: string | null;
  estatusNuevo: string;
  /** null = proceso automatico. */
  usuarioNombre: string | null;
  detalle: Record<string, unknown> | null;
}

export interface AuditoriaDecision {
  fechaFirma: string;
  autorizadorNombre: string | null;
  numeroCedula: string | null;
  decision: "APROBAR" | "RECHAZAR";
  motivo: string | null;
  descripcionMotivo: string | null;
  alcanceAplicado: string;
  metodoFirma: string;
  hashContenido: string;
  /** Firmo el contenido vigente (un recalculo invalida firmas anteriores). */
  firmaVigente: boolean;
  ipOrigen: string | null;
  agenteUsuario: string | null;
  identificadorPeticion: string | null;
}

export interface AuditoriaDestinatario {
  autorizadorNombre: string | null;
  tipoSeleccion: string;
  estatus: string;
  fechaEnvio: string;
  fechaVisto: string | null;
}

export interface AuditoriaLineaDeTiempo {
  solicitud: AuditoriaFila & { hashContenido: string };
  eventos: AuditoriaEvento[];
  decisiones: AuditoriaDecision[];
  destinatarios: AuditoriaDestinatario[];
}
