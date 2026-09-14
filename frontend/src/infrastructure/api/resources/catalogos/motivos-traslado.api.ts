import apiClient from "@api/client";
import type {
  MotivoTrasladoListParams,
  MotivoTrasladoListResponse,
  MotivoTrasladoDetailResponse,
  CreateMotivoTrasladoRequest,
  CreateMotivoTrasladoResponse,
  UpdateMotivoTrasladoRequest,
  UpdateMotivoTrasladoResponse,
  DeleteMotivoTrasladoResponse,
} from "@api/types";

export const motivoTrasladoAPI = {
  getAll: async (params?: MotivoTrasladoListParams): Promise<MotivoTrasladoListResponse> => {
    const response = await apiClient.get<MotivoTrasladoListResponse>("/transfer-reasons/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<MotivoTrasladoDetailResponse> => {
    const response = await apiClient.get<MotivoTrasladoDetailResponse>(`/transfer-reasons/${id}/`);
    return response.data;
  },
  create: async (data: CreateMotivoTrasladoRequest): Promise<CreateMotivoTrasladoResponse> => {
    const response = await apiClient.post<CreateMotivoTrasladoResponse>("/transfer-reasons/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateMotivoTrasladoRequest): Promise<UpdateMotivoTrasladoResponse> => {
    const response = await apiClient.put<UpdateMotivoTrasladoResponse>(`/transfer-reasons/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteMotivoTrasladoResponse> => {
    const response = await apiClient.delete<DeleteMotivoTrasladoResponse>(`/transfer-reasons/${id}/`);
    return response.data;
  },
};
