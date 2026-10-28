import apiClient from "@api/client";
import type {
  CitaListItem,
  CitasListParams,
  CitasListResponse,
  ConfirmarCheckinOptions,
  ConfirmarQRCheckinResponse,
  CreateCitaRequest,
  FichaQRResponse,
  MotivosCancelacionResponse,
  SlotsParams,
  SlotsResponse,
  UpdateEstatusCitaRequest,
} from "@api/types";

export const citasAPI = {

  getAll: async (params?: CitasListParams): Promise<CitasListResponse> => {
    const r = await apiClient.get<CitasListResponse>("/citas", { params });
    return r.data;
  },

  getById: async (id: number): Promise<CitaListItem> => {
    const r = await apiClient.get<CitaListItem>(`/citas/${id}`);
    return r.data;
  },

  create: async (data: CreateCitaRequest): Promise<CitaListItem> => {
    const r = await apiClient.post<CitaListItem>("/citas", data);
    return r.data;
  },

  updateEstatus: async (id: number, data: UpdateEstatusCitaRequest): Promise<CitaListItem> => {
    const r = await apiClient.patch<CitaListItem>(`/citas/${id}/estatus`, data);
    return r.data;
  },

  getMotivosCancelacion: async (): Promise<MotivosCancelacionResponse> => {
    const r = await apiClient.get<MotivosCancelacionResponse>("/citas/motivos-cancelacion");
    return r.data;
  },

  getSlots: async (params: SlotsParams): Promise<SlotsResponse> => {
    const r = await apiClient.get<SlotsResponse>("/citas/slots", { params });
    return r.data;
  },

  // ── Check-in por QR (Fase 7 "Citas en Línea") ────────────────────────────
  // `payload` es el string crudo leído del QR ("{folio}:{firma}"); se
  // reenvía tal cual en ambos pasos, el backend re-valida la firma HMAC
  // en cada llamada (nunca se confía en un folio suelto del cliente).

  verificarQR: async (payload: string): Promise<FichaQRResponse> => {
    const r = await apiClient.post<FichaQRResponse>("/citas/verificar-qr", { payload });
    return r.data;
  },

  confirmarVerificacionQR: async (
    payload: string,
    options: ConfirmarCheckinOptions = {},
  ): Promise<ConfirmarQRCheckinResponse> => {
    const r = await apiClient.post<ConfirmarQRCheckinResponse>(
      "/citas/verificar-qr/confirmar",
      { payload, ...options },
    );
    return r.data;
  },
};
