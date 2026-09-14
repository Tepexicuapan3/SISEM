import apiClient from "@api/client";
import type { LegacyConsultationHistoryResponse } from "@api/types/legacy-consultation.types";

export const legacyConsultationAPI = {
  getForPatient: async (
    noExp: string,
    pkNum = 0,
  ): Promise<LegacyConsultationHistoryResponse> => {
    const response = await apiClient.get<LegacyConsultationHistoryResponse>(
      `/patients/${noExp}/legacy-consultations`,
      { params: { pkNum } },
    );
    return response.data;
  },
};
