import apiClient from "@api/client";
import type {
  AmbulanceRequestItem,
  AmbulanceRequestListParams,
  AmbulanceRequestListResponse,
  AuthorizeAmbulanceRequestRequest,
  CreateAmbulanceRequestRequest,
  RejectAmbulanceRequestRequest,
} from "@api/types";

export const ambulanciasAPI = {
  getAll: async (params?: AmbulanceRequestListParams): Promise<AmbulanceRequestListResponse> => {
    const response = await apiClient.get<AmbulanceRequestListResponse>("/ambulance-requests", { params });
    return response.data;
  },

  create: async (data: CreateAmbulanceRequestRequest): Promise<AmbulanceRequestItem> => {
    const response = await apiClient.post<AmbulanceRequestItem>("/ambulance-requests", data);
    return response.data;
  },

  authorize: async (id: number, data: AuthorizeAmbulanceRequestRequest): Promise<AmbulanceRequestItem> => {
    const response = await apiClient.patch<AmbulanceRequestItem>(`/ambulance-requests/${id}/authorize`, data);
    return response.data;
  },

  reject: async (id: number, data: RejectAmbulanceRequestRequest): Promise<AmbulanceRequestItem> => {
    const response = await apiClient.patch<AmbulanceRequestItem>(`/ambulance-requests/${id}/reject`, data);
    return response.data;
  },

  cancel: async (id: number): Promise<AmbulanceRequestItem> => {
    const response = await apiClient.patch<AmbulanceRequestItem>(`/ambulance-requests/${id}/cancel`, {});
    return response.data;
  },
};
