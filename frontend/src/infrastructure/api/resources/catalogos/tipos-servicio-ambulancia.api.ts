import apiClient from "@api/client";
import type {
  TipoServicioAmbulanciaListParams,
  TipoServicioAmbulanciaListResponse,
  TipoServicioAmbulanciaDetailResponse,
  CreateTipoServicioAmbulanciaRequest,
  CreateTipoServicioAmbulanciaResponse,
  UpdateTipoServicioAmbulanciaRequest,
  UpdateTipoServicioAmbulanciaResponse,
  DeleteTipoServicioAmbulanciaResponse,
} from "@api/types";

export const tipoServicioAmbulanciaAPI = {
  getAll: async (params?: TipoServicioAmbulanciaListParams): Promise<TipoServicioAmbulanciaListResponse> => {
    const response = await apiClient.get<TipoServicioAmbulanciaListResponse>("/ambulance-service-types/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<TipoServicioAmbulanciaDetailResponse> => {
    const response = await apiClient.get<TipoServicioAmbulanciaDetailResponse>(`/ambulance-service-types/${id}/`);
    return response.data;
  },
  create: async (data: CreateTipoServicioAmbulanciaRequest): Promise<CreateTipoServicioAmbulanciaResponse> => {
    const response = await apiClient.post<CreateTipoServicioAmbulanciaResponse>("/ambulance-service-types/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateTipoServicioAmbulanciaRequest): Promise<UpdateTipoServicioAmbulanciaResponse> => {
    const response = await apiClient.put<UpdateTipoServicioAmbulanciaResponse>(`/ambulance-service-types/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteTipoServicioAmbulanciaResponse> => {
    const response = await apiClient.delete<DeleteTipoServicioAmbulanciaResponse>(`/ambulance-service-types/${id}/`);
    return response.data;
  },
};
