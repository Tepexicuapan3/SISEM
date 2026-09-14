import apiClient from "@api/client";
import type {
  DestinoAmbulanciaListParams,
  DestinoAmbulanciaListResponse,
  DestinoAmbulanciaDetailResponse,
  CreateDestinoAmbulanciaRequest,
  CreateDestinoAmbulanciaResponse,
  UpdateDestinoAmbulanciaRequest,
  UpdateDestinoAmbulanciaResponse,
  DeleteDestinoAmbulanciaResponse,
} from "@api/types";

export const destinoAmbulanciaAPI = {
  getAll: async (params?: DestinoAmbulanciaListParams): Promise<DestinoAmbulanciaListResponse> => {
    const response = await apiClient.get<DestinoAmbulanciaListResponse>("/ambulance-destinations/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<DestinoAmbulanciaDetailResponse> => {
    const response = await apiClient.get<DestinoAmbulanciaDetailResponse>(`/ambulance-destinations/${id}/`);
    return response.data;
  },
  create: async (data: CreateDestinoAmbulanciaRequest): Promise<CreateDestinoAmbulanciaResponse> => {
    const response = await apiClient.post<CreateDestinoAmbulanciaResponse>("/ambulance-destinations/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateDestinoAmbulanciaRequest): Promise<UpdateDestinoAmbulanciaResponse> => {
    const response = await apiClient.put<UpdateDestinoAmbulanciaResponse>(`/ambulance-destinations/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteDestinoAmbulanciaResponse> => {
    const response = await apiClient.delete<DeleteDestinoAmbulanciaResponse>(`/ambulance-destinations/${id}/`);
    return response.data;
  },
};
