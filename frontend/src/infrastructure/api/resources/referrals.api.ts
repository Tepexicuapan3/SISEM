import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  CancelReferralRequest,
  CreateReferralRequest,
  PatientReferralsResponse,
  ReferralItem,
} from "@api/types/referral.types";

export const referralsAPI = {
  getPatientHistory: async (
    noExp: string,
    pkNum = 0,
  ): Promise<PatientReferralsResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `referrals`);
    const response = await apiClient.get<PatientReferralsResponse>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },

  create: async (
    visitId: number,
    data: CreateReferralRequest,
  ): Promise<ReferralItem> => {
    const response = await apiClient.post<ReferralItem>(
      `/visits/${visitId}/referrals`,
      data,
    );
    return response.data;
  },

  cancel: async (
    referralId: number,
    data: CancelReferralRequest,
  ): Promise<ReferralItem> => {
    const response = await apiClient.patch<ReferralItem>(
      `/referrals/${referralId}/cancel`,
      data,
    );
    return response.data;
  },
};
