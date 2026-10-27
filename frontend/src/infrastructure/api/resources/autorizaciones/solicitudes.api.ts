import apiClient from "@api/client";
import type {
  DecisionRequest,
  ElegiblesResponse,
  MotivosRechazoResponse,
  NotificarRequest,
  NotificarResponse,
  SolicitudDetalleResponse,
  SolicitudesListParams,
  SolicitudesListResponse,
} from "@api/types/autorizaciones/solicitudes.types";

const BASE = "/autorizaciones/solicitudes";

export const solicitudesAPI = {
  getAll: async (params?: SolicitudesListParams): Promise<SolicitudesListResponse> => {
    const response = await apiClient.get<SolicitudesListResponse>(`${BASE}/`, { params });
    return response.data;
  },

  getByUuid: async (uuid: string): Promise<SolicitudDetalleResponse> => {
    const response = await apiClient.get<SolicitudDetalleResponse>(`${BASE}/${uuid}/`);
    return response.data;
  },

  decidir: async (uuid: string, data: DecisionRequest): Promise<SolicitudDetalleResponse> => {
    const response = await apiClient.post<SolicitudDetalleResponse>(`${BASE}/${uuid}/decision/`, data);
    return response.data;
  },

  getElegibles: async (uuid: string): Promise<ElegiblesResponse> => {
    const response = await apiClient.get<ElegiblesResponse>(`${BASE}/${uuid}/elegibles/`);
    return response.data;
  },

  notificar: async (uuid: string, data: NotificarRequest): Promise<NotificarResponse> => {
    const response = await apiClient.post<NotificarResponse>(`${BASE}/${uuid}/notificar/`, data);
    return response.data;
  },

  getMotivosRechazo: async (): Promise<MotivosRechazoResponse> => {
    const response = await apiClient.get<MotivosRechazoResponse>("/autorizaciones/motivos-rechazo/");
    return response.data;
  },
};
