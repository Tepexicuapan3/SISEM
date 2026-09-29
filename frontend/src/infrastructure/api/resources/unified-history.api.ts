import apiClient from "@api/client";
import type {
  ClinicalCatalogs,
  HistoricalNotesResponse,
  PatientRecordResource,
  PhysicalExamResponse,
  RecordListResponse,
  SavePhysicalExamRequest,
} from "@api/types/unified-history.types";

/** CRUD generico de los registros permanentes del paciente. */
export const patientRecordsAPI = {
  list: async <T>(resource: PatientRecordResource, noExp: string, pkNum = 0): Promise<RecordListResponse<T>> => {
    const response = await apiClient.get<RecordListResponse<T>>(`/patients/${noExp}/${resource}`, {
      params: { pkNum },
    });
    return response.data;
  },

  create: async <T>(resource: PatientRecordResource, noExp: string, pkNum: number, data: object): Promise<T> => {
    const response = await apiClient.post<T>(`/patients/${noExp}/${resource}`, data, { params: { pkNum } });
    return response.data;
  },

  update: async <T>(
    resource: PatientRecordResource,
    noExp: string,
    pkNum: number,
    recordId: number,
    data: object,
  ): Promise<T> => {
    const response = await apiClient.patch<T>(`/patients/${noExp}/${resource}/${recordId}`, data, {
      params: { pkNum },
    });
    return response.data;
  },

  /** Baja logica: el motivo es obligatorio (nada se borra sin rastro). */
  deactivate: async (
    resource: PatientRecordResource,
    noExp: string,
    pkNum: number,
    recordId: number,
    reason: string,
  ): Promise<void> => {
    await apiClient.delete(`/patients/${noExp}/${resource}/${recordId}`, {
      params: { pkNum },
      data: { reason },
    });
  },
};

export const historicalNotesAPI = {
  list: async (
    noExp: string,
    pkNum = 0,
    filters: { section?: string; specialty?: string } = {},
  ): Promise<HistoricalNotesResponse> => {
    const response = await apiClient.get<HistoricalNotesResponse>(`/patients/${noExp}/historical-notes`, {
      params: { pkNum, ...filters },
    });
    return response.data;
  },
};

export const physicalExamAPI = {
  get: async (visitId: number): Promise<PhysicalExamResponse> => {
    const response = await apiClient.get<PhysicalExamResponse>(`/visits/${visitId}/consultation/physical-exam`);
    return response.data;
  },

  save: async (visitId: number, data: SavePhysicalExamRequest): Promise<PhysicalExamResponse> => {
    const response = await apiClient.put<PhysicalExamResponse>(
      `/visits/${visitId}/consultation/physical-exam`,
      data,
    );
    return response.data;
  },
};

export const clinicalCatalogsAPI = {
  get: async (): Promise<ClinicalCatalogs> => {
    const response = await apiClient.get<ClinicalCatalogs>("/clinical-catalogs");
    return response.data;
  },
};
