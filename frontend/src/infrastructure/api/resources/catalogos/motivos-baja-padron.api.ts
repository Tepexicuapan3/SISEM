import apiClient from "@api/client";
import type {
  MotivoBajaPadronListParams,
  MotivoBajaPadronListResponse,
  MotivoBajaPadronDetailResponse,
  CreateMotivoBajaPadronRequest,
  CreateMotivoBajaPadronResponse,
  UpdateMotivoBajaPadronRequest,
  UpdateMotivoBajaPadronResponse,
  DeleteMotivoBajaPadronResponse,
} from "@api/types";

export const motivoBajaPadronAPI = {
  getAll: async (params?: MotivoBajaPadronListParams): Promise<MotivoBajaPadronListResponse> => {
    const response = await apiClient.get<MotivoBajaPadronListResponse>("/registry-discharge-reasons/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<MotivoBajaPadronDetailResponse> => {
    const response = await apiClient.get<MotivoBajaPadronDetailResponse>(`/registry-discharge-reasons/${id}/`);
    return response.data;
  },
  create: async (data: CreateMotivoBajaPadronRequest): Promise<CreateMotivoBajaPadronResponse> => {
    const response = await apiClient.post<CreateMotivoBajaPadronResponse>("/registry-discharge-reasons/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateMotivoBajaPadronRequest): Promise<UpdateMotivoBajaPadronResponse> => {
    const response = await apiClient.put<UpdateMotivoBajaPadronResponse>(`/registry-discharge-reasons/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteMotivoBajaPadronResponse> => {
    const response = await apiClient.delete<DeleteMotivoBajaPadronResponse>(`/registry-discharge-reasons/${id}/`);
    return response.data;
  },
};
