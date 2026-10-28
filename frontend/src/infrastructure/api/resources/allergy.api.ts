import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  Allergy,
  ChangeAllergyStatusRequest,
  CreateAllergyRequest,
  PatientAllergiesResponse,
  UpdateAllergyRequest,
} from "@api/types/allergy.types";

export const allergyAPI = {
  list: async (noExp: string, pkNum = 0): Promise<PatientAllergiesResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `allergies`);
    const response = await apiClient.get<PatientAllergiesResponse>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },

  create: async (
    noExp: string,
    pkNum: number,
    data: CreateAllergyRequest,
  ): Promise<Allergy> => {
    const ruta = await rutaPaciente(noExp, pkNum, `allergies`);
    const response = await apiClient.post<Allergy>(
      ruta.url,
      data,
      { params: ruta.params },
    );
    return response.data;
  },

  update: async (
    noExp: string,
    pkNum: number,
    allergyId: number,
    data: UpdateAllergyRequest,
  ): Promise<Allergy> => {
    const ruta = await rutaPaciente(noExp, pkNum, `allergies/${allergyId}`);
    const response = await apiClient.patch<Allergy>(
      ruta.url,
      data,
      { params: ruta.params },
    );
    return response.data;
  },

  changeStatus: async (
    noExp: string,
    pkNum: number,
    allergyId: number,
    data: ChangeAllergyStatusRequest,
  ): Promise<Allergy> => {
    const ruta = await rutaPaciente(noExp, pkNum, `allergies/${allergyId}/status`);
    const response = await apiClient.post<Allergy>(
      ruta.url,
      data,
      { params: ruta.params },
    );
    return response.data;
  },
};
