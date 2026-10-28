import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
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
    const ruta = await rutaPaciente(noExp, pkNum, `legacy-consultations`);
    const response = await apiClient.get<LegacyConsultationHistoryResponse>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },

  getReview: async (noExp: string, pkNum = 0): Promise<LegacyReviewResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `legacy-review`);
    const response = await apiClient.get<LegacyReviewResponse>(ruta.url, {
      params: ruta.params,
    });
    return response.data;
  },

  confirmReview: async (
    noExp: string,
    pkNum: number,
    data: ConfirmLegacyReviewRequest,
  ): Promise<ConfirmLegacyReviewResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `legacy-review`);
    const response = await apiClient.post<ConfirmLegacyReviewResponse>(
      ruta.url,
      data,
      { params: ruta.params },
    );
    return response.data;
  },
};
