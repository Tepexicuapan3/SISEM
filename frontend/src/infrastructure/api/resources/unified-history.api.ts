import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  BloodTypeResponse,
  ClinicalCatalogs,
  HistoricalNotesResponse,
  PatientRecordResource,
  PhysicalExamResponse,
  RecordListResponse,
  SaveBloodTypeRequest,
  SavePhysicalExamRequest,
} from "@api/types/unified-history.types";

/** CRUD generico de los registros permanentes del paciente. */
export const patientRecordsAPI = {
  list: async <T>(resource: PatientRecordResource, noExp: string, pkNum = 0): Promise<RecordListResponse<T>> => {
    const ruta = await rutaPaciente(noExp, pkNum, `${resource}`);
    const response = await apiClient.get<RecordListResponse<T>>(ruta.url, {
      params: ruta.params,
    });
    return response.data;
  },

  create: async <T>(resource: PatientRecordResource, noExp: string, pkNum: number, data: object): Promise<T> => {
    const ruta = await rutaPaciente(noExp, pkNum, `${resource}`);
    const response = await apiClient.post<T>(ruta.url, data, { params: ruta.params });
    return response.data;
  },

  update: async <T>(
    resource: PatientRecordResource,
    noExp: string,
    pkNum: number,
    recordId: number,
    data: object,
  ): Promise<T> => {
    const ruta = await rutaPaciente(noExp, pkNum, `${resource}/${recordId}`);
    const response = await apiClient.patch<T>(ruta.url, data, {
      params: ruta.params,
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
    const ruta = await rutaPaciente(noExp, pkNum, `${resource}/${recordId}`);
    await apiClient.delete(ruta.url, {
      params: ruta.params,
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
    const ruta = await rutaPaciente(noExp, pkNum, `historical-notes`);
    const response = await apiClient.get<HistoricalNotesResponse>(ruta.url, {
      params: { ...ruta.params, ...filters },
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

/** GRUPO_SANGUINEO (5.2): vigente + historial; PUT captura o corrige. */
export const bloodTypeAPI = {
  get: async (noExp: string, pkNum = 0): Promise<BloodTypeResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `blood-type`);
    const response = await apiClient.get<BloodTypeResponse>(ruta.url, {
      params: ruta.params,
    });
    return response.data;
  },

  save: async (noExp: string, pkNum: number, data: SaveBloodTypeRequest): Promise<BloodTypeResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `blood-type`);
    const response = await apiClient.put<BloodTypeResponse>(ruta.url, data, {
      params: ruta.params,
    });
    return response.data;
  },
};

export const clinicalCatalogsAPI = {
  get: async (): Promise<ClinicalCatalogs> => {
    const response = await apiClient.get<ClinicalCatalogs>("/clinical-catalogs");
    return response.data;
  },
};
