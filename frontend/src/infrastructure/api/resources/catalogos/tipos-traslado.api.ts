import apiClient from "@api/client";
import type {
  TipoTrasladoListParams,
  TipoTrasladoListResponse,
  TipoTrasladoDetailResponse,
  CreateTipoTrasladoRequest,
  CreateTipoTrasladoResponse,
  UpdateTipoTrasladoRequest,
  UpdateTipoTrasladoResponse,
  DeleteTipoTrasladoResponse,
} from "@api/types";

export const tipoTrasladoAPI = {
  getAll: async (params?: TipoTrasladoListParams): Promise<TipoTrasladoListResponse> => {
    const response = await apiClient.get<TipoTrasladoListResponse>("/transfer-types/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<TipoTrasladoDetailResponse> => {
    const response = await apiClient.get<TipoTrasladoDetailResponse>(`/transfer-types/${id}/`);
    return response.data;
  },
  create: async (data: CreateTipoTrasladoRequest): Promise<CreateTipoTrasladoResponse> => {
    const response = await apiClient.post<CreateTipoTrasladoResponse>("/transfer-types/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateTipoTrasladoRequest): Promise<UpdateTipoTrasladoResponse> => {
    const response = await apiClient.put<UpdateTipoTrasladoResponse>(`/transfer-types/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteTipoTrasladoResponse> => {
    const response = await apiClient.delete<DeleteTipoTrasladoResponse>(`/transfer-types/${id}/`);
    return response.data;
  },
};
