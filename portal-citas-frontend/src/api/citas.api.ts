/**
 * Reserva de cita del portal (Fase 4 del backend / F3 del frontend).
 *
 * Contrato confirmado leyendo el código real del backend (NO asumido):
 *   - Ruta: backend/apps/portal_citas/urls.py:38 (POST /portal/citas).
 *   - Vista: backend/apps/portal_citas/views.py:260-304 (ReservarCitaView,
 *     misma auth Bearer que el resto del portal). `csrf_exempt` porque el
 *     portal no usa cookie de sesión.
 *   - Body: backend/apps/portal_citas/serializers.py:32-37
 *     (`ReservarCitaSerializer`) — `{miembroId: UUID, slotId: int (>=1),
 *     motivo?: string (<=255, blanco permitido)}`.
 *   - Éxito: 201 Created. Shape devuelto por
 *     backend/apps/portal_citas/uses_case/reservar_cita_usecase.py
 *     — `{folio, fechaHora (ISO 8601), consultorioNombre, servicioTipo}`.
 *     Nunca incluye no_exp/pk_num ni datos de otros pacientes (ver
 *     docstring del usecase). Tampoco incluye `medicoNombre`: el portal
 *     público de pacientes no muestra el nombre del médico en ningún
 *     punto del flujo — eso solo lo ve recepción en el check-in por QR.
 *
 * Errores de dominio posibles (backend/apps/portal_citas/errors.py,
 * `PortalReservaError` con el mismo contrato `code`/`message`/`status_code`
 * que ya normaliza `@/api/client.ts` en `ApiError`):
 *   - `VALIDATION_ERROR` (422) — body inválido (views.py:277-284).
 *   - `NO_AUTORIZADO` (403) — el miembroId no está entre los que la sesión
 *     puede gestionar, o no existe (usecase:87-91). Mensaje genérico a
 *     propósito (no distingue "no existe" de "no autorizado").
 *   - `SLOT_NO_DISPONIBLE` (409) — el slot ya no está libre, no existe, o no
 *     es apto para portal (usecase:108-112). El usuario debe elegir otro
 *     horario.
 *   - `HORARIO_PASADO` (409) — la fecha y hora del slot ya pasó (el paciente
 *     dejó la pantalla abierta). Igual que `SLOT_NO_DISPONIBLE`: elegir
 *     otro horario.
 *   - `MEDICO_NO_DISPONIBLE` (409) — el médico tiene una ausencia en ese
 *     horario (vacaciones, hora de comida, etc.). Elegir otro horario.
 *   - `SIN_VIGENCIA` (403) — la persona no tiene vigencia activa.
 *   - `CLINICA_NO_CORRESPONDE` (403) — el consultorio no es de la clínica
 *     del paciente. Elegir otro horario.
 *   - `CITA_MISMO_DIA` / `TOPE_EXPEDIENTE_DIA` / `TOPE_CITAS_FUTURAS` (409)
 *     — topes de citas; el mensaje del backend dice cuál.
 *   - `CITA_SUPERPUESTA` (409) — el mismo paciente ya tiene otra cita
 *     activa (AGENDADA/CONFIRMADA) que se cruza en el tiempo con este slot
 *     (usecase:127-137). Distinto de `SLOT_NO_DISPONIBLE`: acá el slot en sí
 *     sigue libre, el problema es el paciente.
 *   - `INTERNAL_SERVER_ERROR` (500) — error inesperado (views.py:295-302).
 */

import apiClient from "@/api/client";

export interface ReservarCitaParams {
  miembroId: string;
  slotId: number;
  /** Opcional y libre — se manda `undefined` si está vacío (el backend lo trata como `None`). */
  motivo?: string;
}

export interface ReservaCitaResult {
  folio: string;
  /** ISO 8601 (`cita.fecha_hora.isoformat()`). */
  fechaHora: string;
  consultorioNombre: string | null;
  servicioTipo: "especialidad" | "medicina_general";
}

export function reservarCita({
  miembroId,
  slotId,
  motivo,
}: ReservarCitaParams): Promise<ReservaCitaResult> {
  return apiClient
    .post<ReservaCitaResult>("/portal/citas", {
      miembroId,
      slotId,
      motivo: motivo && motivo.trim() !== "" ? motivo.trim() : undefined,
    })
    .then((res) => res.data);
}

/**
 * Listado de citas del núcleo (Fase 8 del backend / F4 del frontend).
 *
 * Contrato confirmado leyendo el código real del backend (NO asumido):
 *   - Ruta: backend/apps/portal_citas/urls.py:38 — mismo path
 *     `/portal/citas`, distinto verbo HTTP (`GET`) que la reserva (`POST`);
 *     no hay una ruta nueva en `urls.py`, ver el docstring de
 *     `ReservarCitaView` en views.py:262-281.
 *   - Vista: backend/apps/portal_citas/views.py:286-287 (`ReservarCitaView.get`).
 *   - Shape: backend/apps/portal_citas/uses_case/listar_citas_usecase.py
 *     — `{citas: [{folio, fechaHora (ISO 8601), consultorioNombre,
 *     servicioTipo, estatus, paraQuien, cancelable}]}`. Sin `medicoNombre`:
 *     el portal público no muestra el nombre del médico en ningún punto.
 *     `estatus` es uno de los valores de `EstatusCita`
 *     (backend/apps/recepcion/models.py:24-29): `agendada` | `confirmada` |
 *     `atendida` | `cancelada` | `no_asistio`. `cancelable` ya viene
 *     calculado por el backend (mismo criterio que `cancelar_cita_usecase`:
 *     estatus cancelable + ventana mínima de horas) — el frontend NO debe
 *     reimplementar esa regla, solo leer el booleano.
 *   - Sin errores de dominio propios: requiere sesión válida (401 genérico
 *     si el token venció/es inválido, manejado ya por `client.ts`).
 */
export type EstatusCitaPortal =
  | "agendada"
  | "confirmada"
  | "atendida"
  | "cancelada"
  | "no_asistio";

export interface CitaPortal {
  folio: string;
  /** ISO 8601 (`cita.fecha_hora.isoformat()`). */
  fechaHora: string;
  consultorioNombre: string | null;
  servicioTipo: "especialidad" | "medicina_general";
  estatus: EstatusCitaPortal;
  paraQuien: string | null;
  cancelable: boolean;
}

export function listarCitas(): Promise<CitaPortal[]> {
  return apiClient
    .get<{ citas: CitaPortal[] }>("/portal/citas")
    .then((res) => res.data.citas);
}

/**
 * Cancelación de cita (Fase 6 del backend / F4 del frontend).
 *
 * Contrato confirmado leyendo el código real del backend (NO asumido):
 *   - Ruta: backend/apps/portal_citas/urls.py:41-45
 *     (`PATCH /portal/citas/{folio}/cancelar`).
 *   - Vista: backend/apps/portal_citas/views.py:324-366 (`CancelarCitaView`).
 *   - Body: backend/apps/portal_citas/serializers.py:40-43
 *     (`CancelarCitaSerializer`) — `{motivo?: string (<=500, blanco
 *     permitido)}`.
 *   - Éxito: 200 OK. Shape devuelto por
 *     backend/apps/portal_citas/uses_case/cancelar_cita_usecase.py:170
 *     — `{folio, estatus}` (siempre `"cancelada"` si no lanzó excepción).
 *
 * Errores de dominio posibles (backend/apps/portal_citas/errors.py,
 * `PortalCancelacionError`, mismo contrato `code`/`message`/`status_code`
 * que ya normaliza `client.ts` en `ApiError` — códigos EXACTOS leídos de
 * cancelar_cita_usecase.py):
 *   - `CITA_NO_ENCONTRADA` (404) — el folio no existe (usecase:84-89).
 *   - `NO_AUTORIZADO` (403) — la cita no es de un miembro que la sesión
 *     actual puede gestionar, o el miembro no existe (usecase:97-104).
 *     Mensaje genérico a propósito (no distingue el motivo).
 *   - `ESTADO_NO_CANCELABLE` (409) — la cita ya está `atendida`,
 *     `cancelada` o `no_asistio` (usecase:69-75). El mensaje del backend ya
 *     incluye el estatus actual.
 *   - `FUERA_DE_VENTANA` (409) — falta menos de
 *     `PORTAL_CANCELACION_VENTANA_HORAS` horas para la cita (usecase:110-115).
 *   - `VALIDATION_ERROR` (422) — `motivo` inválido (views.py:340-347).
 *   - `INTERNAL_SERVER_ERROR` (500) — error inesperado (views.py:358-365).
 */
export interface CancelarCitaResult {
  folio: string;
  estatus: EstatusCitaPortal;
}

export function cancelarCita(
  folio: string,
  motivo?: string
): Promise<CancelarCitaResult> {
  return apiClient
    .patch<CancelarCitaResult>(`/portal/citas/${encodeURIComponent(folio)}/cancelar`, {
      motivo: motivo && motivo.trim() !== "" ? motivo.trim() : undefined,
    })
    .then((res) => res.data);
}
