import apiClient from "@api/client";
import type {
  CheckinCandidatosParams,
  CheckinCandidatosResponse,
  ConfirmarCheckinOptions,
  ConfirmarQRCheckinResponse,
} from "@api/types";

/**
 * Check-in manual (sin QR): buscador por nombre o folio de la cita.
 * `GET .../checkin/candidatos` y `POST .../checkin/confirmar-folio` viven
 * bajo el recurso `/citas` (ver `backend/apps/recepcion/views/qr_checkin_views.py`),
 * el mismo que expone el check-in por QR en `citas.api.ts` — se separan en
 * este archivo solo porque son un flujo distinto (sin payload firmado), no
 * porque el backend los sirva desde otro recurso.
 */
export const checkinAPI = {
  buscarCandidatos: async (
    params: CheckinCandidatosParams,
  ): Promise<CheckinCandidatosResponse> => {
    const r = await apiClient.get<CheckinCandidatosResponse>(
      "/citas/checkin/candidatos",
      { params },
    );
    return r.data;
  },

  // Response idéntico al de `citasAPI.confirmarVerificacionQR` — el backend
  // reusa el mismo `checkin_por_folio` para ambos flujos.
  confirmarFolio: async (
    folio: string,
    options: ConfirmarCheckinOptions = {},
  ): Promise<ConfirmarQRCheckinResponse> => {
    const r = await apiClient.post<ConfirmarQRCheckinResponse>(
      "/citas/checkin/confirmar-folio",
      { folio, ...options },
    );
    return r.data;
  },
};
