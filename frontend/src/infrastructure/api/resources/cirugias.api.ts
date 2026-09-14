import apiClient from "@api/client";
import type {
  CancelSurgeryRequest,
  ScheduleSurgeryRequest,
  SurgeryItem,
  SurgeryListParams,
  SurgeryListResponse,
} from "@api/types";

export const cirugiasAPI = {
  getAll: async (params?: SurgeryListParams): Promise<SurgeryListResponse> => {
    const response = await apiClient.get<SurgeryListResponse>("/surgeries", { params });
    return response.data;
  },

  schedule: async (data: ScheduleSurgeryRequest): Promise<SurgeryItem> => {
    const response = await apiClient.post<SurgeryItem>("/surgeries", data);
    return response.data;
  },

  cancel: async (id: number, data: CancelSurgeryRequest): Promise<SurgeryItem> => {
    const response = await apiClient.patch<SurgeryItem>(`/surgeries/${id}/cancel`, data);
    return response.data;
  },
};
