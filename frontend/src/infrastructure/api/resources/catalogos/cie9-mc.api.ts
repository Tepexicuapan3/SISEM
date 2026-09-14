import apiClient from "@api/client";
import type {
  Cie9McListParams,
  Cie9McListResponse,
  Cie9McDetailResponse,
  CreateCie9McRequest,
  CreateCie9McResponse,
  UpdateCie9McRequest,
  UpdateCie9McResponse,
  DeleteCie9McResponse,
} from "@api/types";

export const cie9McAPI = {
  getAll: async (params?: Cie9McListParams): Promise<Cie9McListResponse> => {
    const response = await apiClient.get<Cie9McListResponse>("/cie9-mc/", { params });
    return response.data;
  },

  getById: async (id: number): Promise<Cie9McDetailResponse> => {
    const response = await apiClient.get<Cie9McDetailResponse>(`/cie9-mc/${id}/`);
    return response.data;
  },

  create: async (data: CreateCie9McRequest): Promise<CreateCie9McResponse> => {
    const response = await apiClient.post<CreateCie9McResponse>("/cie9-mc/", data);
    return response.data;
  },

  update: async (id: number, data: UpdateCie9McRequest): Promise<UpdateCie9McResponse> => {
    const response = await apiClient.put<UpdateCie9McResponse>(`/cie9-mc/${id}/`, data);
    return response.data;
  },

  delete: async (id: number): Promise<DeleteCie9McResponse> => {
    const response = await apiClient.delete<DeleteCie9McResponse>(`/cie9-mc/${id}/`);
    return response.data;
  },
};
