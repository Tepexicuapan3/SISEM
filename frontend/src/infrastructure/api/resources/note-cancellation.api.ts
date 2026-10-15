import apiClient from "@api/client";
import type {
  CancelConsultationNoteRequest,
  CancelConsultationNoteResponse,
  NoteCancellationPreview,
} from "@api/types/note-cancellation.types";

export const noteCancellationAPI = {
  getPreview: async (visitId: number): Promise<NoteCancellationPreview> => {
    const r = await apiClient.get<NoteCancellationPreview>(
      `/visits/${visitId}/consultation/cancellation-preview`,
    );
    return r.data;
  },

  // Contrasena erronea => 403 REAUTH_FAILED (nunca 401): el interceptor no
  // dispara refresh ni logout.
  cancel: async (
    visitId: number,
    data: CancelConsultationNoteRequest,
  ): Promise<CancelConsultationNoteResponse> => {
    const r = await apiClient.post<CancelConsultationNoteResponse>(
      `/visits/${visitId}/consultation/cancel`,
      data,
    );
    return r.data;
  },
};
