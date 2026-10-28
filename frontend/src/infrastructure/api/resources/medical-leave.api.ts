import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  CreateMedicalLeaveRequest,
  MedicalLeaveItem,
  PatientMedicalLeavesResponse,
} from "@api/types/medical-leave.types";

export const medicalLeaveAPI = {
  getPatientHistory: async (
    noExp: string,
    pkNum = 0,
  ): Promise<PatientMedicalLeavesResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `medical-leaves`);
    const response = await apiClient.get<PatientMedicalLeavesResponse>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },

  create: async (
    visitId: number,
    data: CreateMedicalLeaveRequest,
  ): Promise<MedicalLeaveItem> => {
    const response = await apiClient.post<MedicalLeaveItem>(
      `/visits/${visitId}/medical-leave`,
      data,
    );
    return response.data;
  },
};
