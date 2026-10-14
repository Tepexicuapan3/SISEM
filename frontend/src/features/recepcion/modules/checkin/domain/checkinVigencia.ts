import { ApiError } from "@api/utils/errors";
import type { ConfirmarCheckinOptions } from "@api/types";

/**
 * Check-in de un paciente sin vigencia (`PACIENTE_SIN_VIGENCIA`,
 * `backend/apps/recepcion/uses_case/qr_checkin_usecase.py`): la cita no se
 * cancela; se confirma solo con el motivo u oficio de Capital Humano.
 */

/** El check-in sin vigencia necesita un motivo no vacío. */
export const autorizacionVigenciaCompleta = (vigenciaActiva: boolean, autorizacion: string) =>
  vigenciaActiva || autorizacion.trim().length > 0;

/** Solo se manda la autorización cuando hace falta. */
export const buildConfirmarCheckinOptions = (
  vigenciaActiva: boolean,
  autorizacion: string,
): ConfirmarCheckinOptions =>
  vigenciaActiva ? {} : { autorizacionCapitalHumano: autorizacion.trim() };

/** La vigencia cambió entre la búsqueda y la confirmación: hay que pedir la autorización. */
export const esErrorSinVigencia = (error: unknown) =>
  error instanceof ApiError && error.code === "PACIENTE_SIN_VIGENCIA";
