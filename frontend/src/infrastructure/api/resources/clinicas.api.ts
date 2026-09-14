import apiClient from "@api/client";
import type { ClinicasListResponse } from "@api/types";

export const clinicasAPI = {
  getAll: async (): Promise<ClinicasListResponse> => {
    const response = await apiClient.get<ClinicasListResponse>("/clinicas");
    return response.data;
  },
};
