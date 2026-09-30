import type { ListResponse } from "@api/types/common.types";
import type { VisitQueueItem, VisitService } from "@api/types/visits.types";

// ─── Constantes ───────────────────────────────────────────────────────────────

export const ESTATUS_CITA = {
  AGENDADA:   "agendada",
  CONFIRMADA: "confirmada",
  ATENDIDA:   "atendida",
  CANCELADA:  "cancelada",
  NO_ASISTIO: "no_asistio",
} as const;

export type EstatusCita = (typeof ESTATUS_CITA)[keyof typeof ESTATUS_CITA];

// ─── Entidades ────────────────────────────────────────────────────────────────

export const ORIGEN_CANAL_CITA = {
  RECEPCION: "RECEPCION",
  PORTAL:    "PORTAL",
} as const;

/** Origen de la cita: agendada en recepción vs reservada por el paciente desde el portal de citas en línea. */
export type OrigenCanalCita = (typeof ORIGEN_CANAL_CITA)[keyof typeof ORIGEN_CANAL_CITA];

export interface CitaListItem {
  id:                 number;
  folio:              string;
  noExp:              string;
  pkNum:              number;
  medicoId:           number;
  medicoNombre:       string;
  consultorioId:      number | null;
  consultorioNombre:  string | null;
  fechaHora:          string;   // ISO 8601
  duracionMin:        number;
  servicioTipo:       VisitService;
  estatus:            EstatusCita;
  motivo:             string | null;
  notas:              string | null;
  createdAt:          string;
  /** "RECEPCION" | "PORTAL" — distingue las citas reservadas desde el portal en línea. */
  origenCanal:        OrigenCanalCita;
}

export interface SlotDisponible {
  fecha:        string;   // YYYY-MM-DD
  hora:         string;   // HH:mm
  duracionMin:  number;
  consultorioId: number | null;
}

// ─── Requests ─────────────────────────────────────────────────────────────────

export interface CreateCitaRequest {
  noExp:         string;
  pkNum?:        number;
  medicoId:      number;
  consultorioId?: number;
  fechaHora:     string;   // YYYY-MM-DDTHH:mm
  duracionMin?:  number;
  servicioTipo?: VisitService;
  motivo?:       string;
  notas?:        string;
}

export interface UpdateEstatusCitaRequest {
  estatus: "confirmada" | "atendida" | "cancelada" | "no_asistio";
  /**
   * Obligatorio para "cancelada" y "no_asistio" — la máquina de estados del
   * backend (cita_state_machine_usecase.transition_cita_state) lo exige y
   * responde 422 CITA_MOTIVO_REQUERIDO si viene vacío.
   */
  motivo?: string;
}

// ─── Params ───────────────────────────────────────────────────────────────────

export interface CitasListParams {
  page?:          number;
  pageSize?:      number;
  medicoId?:      number;
  consultorioId?: number;
  centroId?:      number;
  noExp?:         string;
  folio?:         string;
  estatus?:       EstatusCita;
  fechaDesde?:    string;   // YYYY-MM-DD
  fechaHasta?:    string;   // YYYY-MM-DD
}

export interface SlotsParams {
  medicoId: number;
  fecha:    string;   // YYYY-MM-DD
}

// ─── Responses ────────────────────────────────────────────────────────────────

export type CitasListResponse = ListResponse<CitaListItem>;

export interface SlotsResponse {
  slots: SlotDisponible[];
}

/** Ficha resuelta por `POST /citas/verificar-qr` — solo lectura, sin efectos secundarios. */
export interface FichaQRResponse {
  folio:        string;
  paciente:     string;
  medico:       string;
  consultorio:  string | null;
  fechaHora:    string;   // ISO 8601
  servicioTipo: VisitService;
  motivo:       string | null;
  estatus:      EstatusCita;
  yaVerificada: boolean;
  /** "RECEPCION" | "PORTAL" — distingue las citas reservadas desde el portal en línea. */
  origenCanal:  OrigenCanalCita;
}

/** Resultado de `POST /citas/verificar-qr/confirmar` — crea el Visit y sella la cita como verificada. */
export interface ConfirmarQRCheckinResponse {
  folio:        string;
  paciente:     string;
  verificadoEn: string;   // ISO 8601
  visit:        VisitQueueItem;
}
