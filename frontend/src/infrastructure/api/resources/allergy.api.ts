import apiClient from "@api/client";
import type {
  Allergy,
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

  deactivate: async (
    noExp: string,
    pkNum: number,
    allergyId: number,
  ): Promise<Allergy> => {
    const response = await apiClient.delete<Allergy>(
      `/patients/${noExp}/allergies/${allergyId}`,
      { params: { pkNum } },
    );
    return response.data;
  },
};
