import apiClient from "@api/client";
import type {
  PrescriptionAuthorizationHistoryParams,
  PrescriptionAuthorizationItem,
  PrescriptionAuthorizationListResponse,
  RejectPrescriptionRequest,
} from "@api/types";

export const prescriptionAuthorizationsAPI = {
  getPending: async (): Promise<PrescriptionAuthorizationListResponse> => {
    const response = await apiClient.get<PrescriptionAuthorizationListResponse>(
      "/prescriptions/authorizations/pending",
    );
    return response.data;
  },

  getHistory: async (
    params?: PrescriptionAuthorizationHistoryParams,
  ): Promise<PrescriptionAuthorizationListResponse> => {
    const response = await apiClient.get<PrescriptionAuthorizationListResponse>(
      "/prescriptions/authorizations",
      { params },
    );
    return response.data;
  },

  authorize: async (id: number): Promise<PrescriptionAuthorizationItem> => {
    const response = await apiClient.post<PrescriptionAuthorizationItem>(
      `/prescriptions/authorizations/${id}/authorize`,
    );
    return response.data;
  },

  reject: async (id: number, data: RejectPrescriptionRequest): Promise<PrescriptionAuthorizationItem> => {
    const response = await apiClient.post<PrescriptionAuthorizationItem>(
      `/prescriptions/authorizations/${id}/reject`,
      data,
    );
    return response.data;
  },
};
