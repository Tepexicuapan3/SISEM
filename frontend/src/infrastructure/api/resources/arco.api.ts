import apiClient from "@api/client";
import type {
  ArcoRequestItem,
  ArcoRequestListParams,
  ArcoRequestListResponse,
  ChangeArcoRequestStatusPayload,
  CreateArcoRequestPayload,
} from "@api/types";

export const arcoAPI = {
  getList: async (params: ArcoRequestListParams): Promise<ArcoRequestListResponse> => {
    const { vencidas, ...rest } = params;
    const response = await apiClient.get<ArcoRequestListResponse>("/solicitudes-arco", {
      params: { ...rest, vencidas: vencidas ? "true" : undefined },
    });
    return response.data;
  },

  create: async (data: CreateArcoRequestPayload): Promise<ArcoRequestItem> => {
    const response = await apiClient.post<ArcoRequestItem>("/solicitudes-arco", data);
    return response.data;
  },

  changeStatus: async (
    id: number,
    data: ChangeArcoRequestStatusPayload,
  ): Promise<ArcoRequestItem> => {
    const response = await apiClient.post<ArcoRequestItem>(
      `/solicitudes-arco/${id}/status`,
      data,
    );
    return response.data;
  },
};
