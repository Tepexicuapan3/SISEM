import apiClient from "@api/client";
import type {
  PadronDischargeRequest,
  PadronEnrollRequest,
  PadronEnrollment,
  PadronListParams,
  PadronListResponse,
  PadronOptionsResponse,
  PadronRegistry,
} from "@api/types/padrones.types";

export const padronesAPI = {
  list: async (registry: PadronRegistry, params?: PadronListParams): Promise<PadronListResponse> => {
    const response = await apiClient.get<PadronListResponse>(`/padrones/${registry}`, { params });
    return response.data;
  },

  options: async (registry: PadronRegistry, search: string): Promise<PadronOptionsResponse> => {
    const response = await apiClient.get<PadronOptionsResponse>(`/padrones/${registry}/opciones`, {
      params: { search },
    });
    return response.data;
  },

  enroll: async (registry: PadronRegistry, data: PadronEnrollRequest): Promise<PadronEnrollment> => {
    const response = await apiClient.post<PadronEnrollment>(`/padrones/${registry}`, data);
    return response.data;
  },

  discharge: async (
    registry: PadronRegistry,
    id: number,
    data: PadronDischargeRequest,
  ): Promise<PadronEnrollment> => {
    const response = await apiClient.post<PadronEnrollment>(`/padrones/${registry}/${id}/baja`, data);
    return response.data;
  },
};
