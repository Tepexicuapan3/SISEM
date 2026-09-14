import apiClient from "@api/client";
import type {
  AddConsultationAddendumRequest,
  ConsultationAddendaListResponse,
  ConsultationAddendum,
} from "@api/types/consultation-addendum.types";

export const consultationAddendumAPI = {
  getAll: async (visitId: number): Promise<ConsultationAddendaListResponse> => {
    const r = await apiClient.get<ConsultationAddendaListResponse>(
      `/visits/${visitId}/consultation/addenda`,
    );
    return r.data;
  },

  add: async (
    visitId: number,
    data: AddConsultationAddendumRequest,
  ): Promise<ConsultationAddendum> => {
    const r = await apiClient.post<ConsultationAddendum>(
      `/visits/${visitId}/consultation/addenda`,
      data,
    );
    return r.data;
  },
};
