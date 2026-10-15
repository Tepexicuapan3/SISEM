import apiClient from "@api/client";
import type {
  DeleteDesignacionResponse,
  DesignacionDetailResponse,
  DesignacionesListParams,
  DesignacionesListResponse,
  DesignacionWriteRequest,
} from "@api/types";

export const authorizerDesignationsAPI = {
  getAll: async (
    params?: DesignacionesListParams,
  ): Promise<DesignacionesListResponse> => {
    const response = await apiClient.get<DesignacionesListResponse>(
      "/authorizer-designations/",
      { params },
    );
    return response.data;
  },

  getById: async (id: number): Promise<DesignacionDetailResponse> => {
    const response = await apiClient.get<DesignacionDetailResponse>(
      `/authorizer-designations/${id}/`,
    );
    return response.data;
  },

  create: async (data: DesignacionWriteRequest): Promise<DesignacionDetailResponse> => {
    const response = await apiClient.post<DesignacionDetailResponse>(
      "/authorizer-designations/",
      data,
    );
    return response.data;
  },

  update: async (
    id: number,
    data: DesignacionWriteRequest,
  ): Promise<DesignacionDetailResponse> => {
    const response = await apiClient.put<DesignacionDetailResponse>(
      `/authorizer-designations/${id}/`,
      data,
    );
    return response.data;
  },

  delete: async (id: number): Promise<DeleteDesignacionResponse> => {
    const response = await apiClient.delete<DeleteDesignacionResponse>(
      `/authorizer-designations/${id}/`,
    );
    return response.data;
  },
};
