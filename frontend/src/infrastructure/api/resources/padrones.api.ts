import apiClient from "@api/client";
import { conIdPaciente } from "@api/paciente-ids";
import type {
  ChronicControlPanel,
  ChronicControlRecord,
  ChronicControlRegisterRequest,
  ChronicVisitEnrollRequest,
  ChronicVisitNotice,
  PadronDischargeRequest,
  PadronEnrollRequest,
  PadronEnrollment,
  PadronListParams,
  PadronListResponse,
  PadronOptionsResponse,
  PadronRegistry,
} from "@api/types/padrones.types";

export const padronesAPI = {
  list: async (registry: PadronRegistry, params?: PadronListParams): Promise<PadronListResponse> => {
    const response = await apiClient.get<PadronListResponse>(`/padrones/${registry}`, { params });
    return response.data;
  },

  options: async (registry: PadronRegistry, search: string): Promise<PadronOptionsResponse> => {
    const response = await apiClient.get<PadronOptionsResponse>(`/padrones/${registry}/opciones`, {
      params: { search },
    });
    return response.data;
  },

  enroll: async (registry: PadronRegistry, data: PadronEnrollRequest): Promise<PadronEnrollment> => {
    const response = await apiClient.post<PadronEnrollment>(`/padrones/${registry}`, await conIdPaciente(data));
    return response.data;
  },

  discharge: async (
    registry: PadronRegistry,
    id: number,
    data: PadronDischargeRequest,
  ): Promise<PadronEnrollment> => {
    const response = await apiClient.post<PadronEnrollment>(`/padrones/${registry}/${id}/baja`, data);
    return response.data;
  },

  chronicVisitNotice: async (visitId: number, cie: string): Promise<ChronicVisitNotice> => {
    const response = await apiClient.get<ChronicVisitNotice>(`/padrones/cronicos/visita/${visitId}/aviso`, {
      params: cie ? { cie } : undefined,
    });
    return response.data;
  },

  enrollChronicFromVisit: async (visitId: number, data: ChronicVisitEnrollRequest): Promise<PadronEnrollment> => {
    const response = await apiClient.post<PadronEnrollment>(`/padrones/cronicos/visita/${visitId}`, data);
    return response.data;
  },

  chronicControlPanel: async (visitId: number): Promise<ChronicControlPanel> => {
    const response = await apiClient.get<ChronicControlPanel>(`/padrones/cronicos/visita/${visitId}/control`);
    return response.data;
  },

  registerChronicControl: async (
    visitId: number,
    data: ChronicControlRegisterRequest,
  ): Promise<ChronicControlRecord> => {
    const response = await apiClient.post<ChronicControlRecord>(`/padrones/cronicos/visita/${visitId}/control`, data);
    return response.data;
  },
};
