import apiClient from "@api/client";
import type { LegacyConsultationHistoryResponse } from "@api/types/legacy-consultation.types";
import type {
  ConfirmLegacyReviewRequest,
  ConfirmLegacyReviewResponse,
  LegacyReviewResponse,
} from "@api/types/legacy-review.types";

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

  getReview: async (noExp: string, pkNum = 0): Promise<LegacyReviewResponse> => {
    const response = await apiClient.get<LegacyReviewResponse>(`/patients/${noExp}/legacy-review`, {
      params: { pkNum },
    });
    return response.data;
  },

  confirmReview: async (
    noExp: string,
    pkNum: number,
    data: ConfirmLegacyReviewRequest,
  ): Promise<ConfirmLegacyReviewResponse> => {
    const response = await apiClient.post<ConfirmLegacyReviewResponse>(
      `/patients/${noExp}/legacy-review`,
      data,
      { params: { pkNum } },
    );
    return response.data;
  },
};
