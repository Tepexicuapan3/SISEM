import apiClient from "@api/client";
import type {
  DailyConsultationReportParams,
  DailyConsultationReportResponse,
} from "@api/types";

export const consultasDiarioReportAPI = {
  getAll: async (
    params?: DailyConsultationReportParams,
  ): Promise<DailyConsultationReportResponse> => {
    const response = await apiClient.get<DailyConsultationReportResponse>(
      "/reportes/consultas/diario",
      { params },
    );
    return response.data;
  },

  exportXlsx: async (params?: DailyConsultationReportParams): Promise<Blob> => {
    const response = await apiClient.get("/reportes/consultas/diario", {
      params: { ...params, export: "xlsx" },
      responseType: "blob",
    });
    return response.data as Blob;
  },
};
