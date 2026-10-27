import apiClient from "@api/client";
import type {
  ContadorNotificacionesResponse,
  MarcarTodasResponse,
  NotificacionesListParams,
  NotificacionesListResponse,
  NotificacionResponse,
} from "@api/types/notificaciones/notificaciones.types";

export const notificacionesAPI = {
  getAll: async (params?: NotificacionesListParams): Promise<NotificacionesListResponse> => {
    const response = await apiClient.get<NotificacionesListResponse>("/notificaciones/", { params });
    return response.data;
  },

  getContador: async (): Promise<ContadorNotificacionesResponse> => {
    const response = await apiClient.get<ContadorNotificacionesResponse>("/notificaciones/contador/");
    return response.data;
  },

  marcarLeida: async (id: number): Promise<NotificacionResponse> => {
    const response = await apiClient.patch<NotificacionResponse>(`/notificaciones/${id}/leida/`);
    return response.data;
  },

  marcarTodasLeidas: async (): Promise<MarcarTodasResponse> => {
    const response = await apiClient.post<MarcarTodasResponse>("/notificaciones/marcar-todas-leidas/");
    return response.data;
  },
};
