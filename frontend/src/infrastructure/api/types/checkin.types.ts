import type { EstatusCita, OrigenCanalCita } from "@api/types/citas.types";

/**
 * Check-in manual (sin QR) — buscador por nombre o folio (Fase 7 "Citas en
 * Línea"). Mismo flujo de negocio que el check-in por QR
 * (`checkin_por_folio` en `apps/recepcion/uses_case/qr_checkin_usecase.py`),
 * solo cambia cómo se resuelve el folio: en vez de decodificar un payload
 * firmado, recepción busca la cita por nombre del paciente o folio y la
 * selecciona de una lista.
 *
 * Endpoints (`backend/apps/recepcion/views/qr_checkin_views.py`):
 *   GET  /citas/checkin/candidatos?nombre=<texto>
 *   GET  /citas/checkin/candidatos?folio=<folio>
 *   POST /citas/checkin/confirmar-folio
 *
 * Viven bajo el mismo recurso `/citas` que el check-in por QR — NO son un
 * recurso `/recepcion/checkin/*` aparte.
 */

/** Cita de HOY elegible para check-in manual — item de la lista de candidatos. */
export interface CheckinCandidato {
  folio: string;
  pacienteNombre: string;
  fechaHora: string; // ISO 8601
  consultorioNombre: string | null;
  medicoNombre: string;
  /** "RECEPCION" | "PORTAL" — distingue las citas reservadas desde el portal en línea. */
  origenCanal: OrigenCanalCita;
  estatus: EstatusCita;
}

/** Búsqueda por nombre (substring, case-insensitive) O por folio exacto — nunca ambos, el backend rechaza cualquier otra combinación. */
export type CheckinCandidatosParams =
  | { nombre: string; folio?: never }
  | { folio: string; nombre?: never };

export interface CheckinCandidatosResponse {
  candidatos: CheckinCandidato[];
}
