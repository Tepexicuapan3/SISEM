import apiClient from "@api/client";
import type { ReferralReportParams, ReferralReportResponse } from "@api/types";

export const pasesReportAPI = {
  getAll: async (params?: ReferralReportParams): Promise<ReferralReportResponse> => {
    const response = await apiClient.get<ReferralReportResponse>("/reportes/pases", {
      params,
    });
    return response.data;
  },

  exportXlsx: async (params?: ReferralReportParams): Promise<Blob> => {
    const response = await apiClient.get("/reportes/pases", {
      params: { ...params, export: "xlsx" },
      responseType: "blob",
    });
    return response.data as Blob;
  },
};
