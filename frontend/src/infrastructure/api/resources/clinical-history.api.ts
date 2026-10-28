import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  ClinicalHistory,
  PatientProfile,
  UpdatePatientProfileRequest,
} from "@api/types/clinical-history.types";

/** HISTORIA_CLINICA (cabecera, solo lectura). */
export const clinicalHistoryAPI = {
  get: async (noExp: string, pkNum = 0): Promise<ClinicalHistory> => {
    const ruta = await rutaPaciente(noExp, pkNum, `clinical-history`);
    const response = await apiClient.get<ClinicalHistory>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },
};

/** PACIENTE (ficha: identidad + datos sociodemograficos). */
export const patientProfileAPI = {
  get: async (noExp: string, pkNum = 0): Promise<PatientProfile> => {
    const ruta = await rutaPaciente(noExp, pkNum, `profile`);
    const response = await apiClient.get<PatientProfile>(ruta.url, {
      params: ruta.params,
    });
    return response.data;
  },

  update: async (
    noExp: string,
    pkNum: number,
    data: UpdatePatientProfileRequest,
  ): Promise<PatientProfile> => {
    const ruta = await rutaPaciente(noExp, pkNum, `profile`);
    const response = await apiClient.patch<PatientProfile>(ruta.url, data, {
      params: ruta.params,
    });
    return response.data;
  },
};
