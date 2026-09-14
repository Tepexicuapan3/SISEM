import apiClient from "@api/client";
import type { AmbulanceReportParams, AmbulanceReportResponse } from "@api/types";

export const ambulanciasReportAPI = {
  getAll: async (params?: AmbulanceReportParams): Promise<AmbulanceReportResponse> => {
    const response = await apiClient.get<AmbulanceReportResponse>("/reportes/ambulancias", { params });
    return response.data;
  },

  exportXlsx: async (params?: AmbulanceReportParams): Promise<Blob> => {
    const response = await apiClient.get("/reportes/ambulancias", {
      params: { ...params, export: "xlsx" },
      responseType: "blob",
    });
    return response.data as Blob;
  },
};
