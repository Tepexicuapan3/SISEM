import apiClient from "@api/client";
import type {
  ClasificacionCirugiaListParams,
  ClasificacionCirugiaListResponse,
  ClasificacionCirugiaDetailResponse,
  CreateClasificacionCirugiaRequest,
  CreateClasificacionCirugiaResponse,
  UpdateClasificacionCirugiaRequest,
  UpdateClasificacionCirugiaResponse,
  DeleteClasificacionCirugiaResponse,
} from "@api/types";

export const clasificacionCirugiaAPI = {
  getAll: async (params?: ClasificacionCirugiaListParams): Promise<ClasificacionCirugiaListResponse> => {
    const response = await apiClient.get<ClasificacionCirugiaListResponse>("/surgery-classifications/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<ClasificacionCirugiaDetailResponse> => {
    const response = await apiClient.get<ClasificacionCirugiaDetailResponse>(`/surgery-classifications/${id}/`);
    return response.data;
  },
  create: async (data: CreateClasificacionCirugiaRequest): Promise<CreateClasificacionCirugiaResponse> => {
    const response = await apiClient.post<CreateClasificacionCirugiaResponse>("/surgery-classifications/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateClasificacionCirugiaRequest): Promise<UpdateClasificacionCirugiaResponse> => {
    const response = await apiClient.put<UpdateClasificacionCirugiaResponse>(`/surgery-classifications/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteClasificacionCirugiaResponse> => {
    const response = await apiClient.delete<DeleteClasificacionCirugiaResponse>(`/surgery-classifications/${id}/`);
    return response.data;
  },
};
