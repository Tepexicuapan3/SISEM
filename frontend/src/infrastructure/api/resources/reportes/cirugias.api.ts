import apiClient from "@api/client";
import type { SurgeryReportParams, SurgeryReportResponse } from "@api/types";

export const cirugiasReportAPI = {
  getAll: async (params?: SurgeryReportParams): Promise<SurgeryReportResponse> => {
    const response = await apiClient.get<SurgeryReportResponse>("/reportes/cirugias", { params });
    return response.data;
  },

  exportXlsx: async (params?: SurgeryReportParams): Promise<Blob> => {
    const response = await apiClient.get("/reportes/cirugias", {
      params: { ...params, export: "xlsx" },
      responseType: "blob",
    });
    return response.data as Blob;
  },
};
