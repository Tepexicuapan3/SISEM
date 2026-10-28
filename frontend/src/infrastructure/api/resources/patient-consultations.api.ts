import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type { PatientConsultationsHistoryResponse } from "@api/types/patient-consultations.types";

export const patientConsultationsAPI = {
  getHistory: async (
    noExp: string,
    pkNum = 0,
  ): Promise<PatientConsultationsHistoryResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `consultations`);
    const response = await apiClient.get<PatientConsultationsHistoryResponse>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },
};
