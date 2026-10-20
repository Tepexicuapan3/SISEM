import apiClient from "@api/client";
import type {
  ParametroDetailResponse,
  ParametrosListResponse,
} from "@api/types/catalogos/parameters.types";

const base = "/parameters/";
const detail = (key: string) => `${base}${encodeURIComponent(key)}/`;

export const parametersAPI = {
  getAll: async (): Promise<ParametrosListResponse> => {
    const response = await apiClient.get<ParametrosListResponse>(base);
    return response.data;
  },

  updateGeneral: async (key: string, value: string): Promise<ParametroDetailResponse> => {
    const response = await apiClient.put<ParametroDetailResponse>(detail(key), { value });
    return response.data;
  },

  setCenterValue: async (
    key: string,
    centerId: number,
    value: string,
  ): Promise<ParametroDetailResponse> => {
    const response = await apiClient.put<ParametroDetailResponse>(
      `${detail(key)}centers/${centerId}/`,
      { value },
    );
    return response.data;
  },

  deleteCenterValue: async (key: string, centerId: number): Promise<ParametroDetailResponse> => {
    const response = await apiClient.delete<ParametroDetailResponse>(
      `${detail(key)}centers/${centerId}/`,
    );
    return response.data;
  },
};
