import apiClient from "@api/client";
import type {
  TipoCirugiaListParams,
  TipoCirugiaListResponse,
  TipoCirugiaDetailResponse,
  CreateTipoCirugiaRequest,
  CreateTipoCirugiaResponse,
  UpdateTipoCirugiaRequest,
  UpdateTipoCirugiaResponse,
  DeleteTipoCirugiaResponse,
} from "@api/types";

export const tipoCirugiaAPI = {
  getAll: async (params?: TipoCirugiaListParams): Promise<TipoCirugiaListResponse> => {
    const response = await apiClient.get<TipoCirugiaListResponse>("/surgery-types/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<TipoCirugiaDetailResponse> => {
    const response = await apiClient.get<TipoCirugiaDetailResponse>(`/surgery-types/${id}/`);
    return response.data;
  },
  create: async (data: CreateTipoCirugiaRequest): Promise<CreateTipoCirugiaResponse> => {
    const response = await apiClient.post<CreateTipoCirugiaResponse>("/surgery-types/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateTipoCirugiaRequest): Promise<UpdateTipoCirugiaResponse> => {
    const response = await apiClient.put<UpdateTipoCirugiaResponse>(`/surgery-types/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteTipoCirugiaResponse> => {
    const response = await apiClient.delete<DeleteTipoCirugiaResponse>(`/surgery-types/${id}/`);
    return response.data;
  },
};
