import apiClient from "@api/client";
import type { MedicalLeaveReportParams, MedicalLeaveReportResponse } from "@api/types";

export const incapacidadesReportAPI = {
  getAll: async (params?: MedicalLeaveReportParams): Promise<MedicalLeaveReportResponse> => {
    const response = await apiClient.get<MedicalLeaveReportResponse>(
      "/reportes/incapacidades",
      { params },
    );
    return response.data;
  },

  exportXlsx: async (params?: MedicalLeaveReportParams): Promise<Blob> => {
    const response = await apiClient.get("/reportes/incapacidades", {
      params: { ...params, export: "xlsx" },
      responseType: "blob",
    });
    return response.data as Blob;
  },
};
