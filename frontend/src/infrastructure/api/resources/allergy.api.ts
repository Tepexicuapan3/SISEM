import apiClient from "@api/client";
import type {
  Allergy,
  ChangeAllergyStatusRequest,
  CreateAllergyRequest,
  PatientAllergiesResponse,
  UpdateAllergyRequest,
} from "@api/types/allergy.types";

export const allergyAPI = {
  list: async (noExp: string, pkNum = 0): Promise<PatientAllergiesResponse> => {
    const response = await apiClient.get<PatientAllergiesResponse>(
      `/patients/${noExp}/allergies`,
      { params: { pkNum } },
    );
    return response.data;
  },

  create: async (
    noExp: string,
    pkNum: number,
    data: CreateAllergyRequest,
  ): Promise<Allergy> => {
    const response = await apiClient.post<Allergy>(
      `/patients/${noExp}/allergies`,
      data,
      { params: { pkNum } },
    );
    return response.data;
  },

  update: async (
    noExp: string,
    pkNum: number,
    allergyId: number,
    data: UpdateAllergyRequest,
  ): Promise<Allergy> => {
    const response = await apiClient.patch<Allergy>(
      `/patients/${noExp}/allergies/${allergyId}`,
      data,
      { params: { pkNum } },
    );
    return response.data;
  },

  changeStatus: async (
    noExp: string,
    pkNum: number,
    allergyId: number,
    data: ChangeAllergyStatusRequest,
  ): Promise<Allergy> => {
    const response = await apiClient.post<Allergy>(
      `/patients/${noExp}/allergies/${allergyId}/status`,
      data,
      { params: { pkNum } },
    );
    return response.data;
  },
};
