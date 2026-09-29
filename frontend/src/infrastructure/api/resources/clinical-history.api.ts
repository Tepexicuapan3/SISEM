import apiClient from "@api/client";
import type {
  ClinicalHistory,
  PatientProfile,
  UpdatePatientProfileRequest,
} from "@api/types/clinical-history.types";

/** HISTORIA_CLINICA (cabecera, solo lectura). */
export const clinicalHistoryAPI = {
  get: async (noExp: string, pkNum = 0): Promise<ClinicalHistory> => {
    const response = await apiClient.get<ClinicalHistory>(
      `/patients/${noExp}/clinical-history`,
      { params: { pkNum } },
    );
    return response.data;
  },
};

/** PACIENTE (ficha: identidad + datos sociodemograficos). */
export const patientProfileAPI = {
  get: async (noExp: string, pkNum = 0): Promise<PatientProfile> => {
    const response = await apiClient.get<PatientProfile>(`/patients/${noExp}/profile`, {
      params: { pkNum },
    });
    return response.data;
  },

  update: async (
    noExp: string,
    pkNum: number,
    data: UpdatePatientProfileRequest,
  ): Promise<PatientProfile> => {
    const response = await apiClient.patch<PatientProfile>(`/patients/${noExp}/profile`, data, {
      params: { pkNum },
    });
    return response.data;
  },
};
