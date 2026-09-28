import apiClient from "@api/client";
import type {
  AddPrescriptionItemRequest,
  AddPrescriptionItemResult,
  AddSecondaryDiagnosisRequest,
  CieSearchParams,
  CieSearchResponse,
  PrescriptionItem,
  SecondaryDiagnosisItem,
  VisitPrescriptionItemsResponse,
  VisitSecondaryDiagnosesResponse,
  CaptureVitalsRequest,
  CaptureVitalsResponse,
  EditVitalsRequest,
  EditVitalsResponse,
  LatestVitalsResponse,
  CloseVisitRequest,
  CloseVisitResponse,
  CreateVisitRequest,
  CreateVisitResponse,
  PatientLookupResponse,
  SaveDiagnosisRequest,
  SaveDiagnosisResponse,
  SavePrescriptionRequest,
  SavePrescriptionResponse,
  StartConsultationResponse,
  UpdateVisitStatusRequest,
  UpdateVisitStatusResponse,
  VisitStatusLogResponse,
  VisitsListParams,
  VisitsListResponse,
} from "@api/types";

export const visitsAPI = {
  getAll: async (params?: VisitsListParams): Promise<VisitsListResponse> => {
    const response = await apiClient.get<VisitsListResponse>("/visits", {
      params,
    });
    return response.data;
  },

  create: async (data: CreateVisitRequest): Promise<CreateVisitResponse> => {
    const response = await apiClient.post<CreateVisitResponse>("/visits", data);
    return response.data;
  },

  updateStatus: async (
    visitId: number,
    data: UpdateVisitStatusRequest,
  ): Promise<UpdateVisitStatusResponse> => {
    const response = await apiClient.patch<UpdateVisitStatusResponse>(
      `/visits/${visitId}/status`,
      data,
    );
    return response.data;
  },

  captureVitals: async (
    visitId: number,
    data: CaptureVitalsRequest,
  ): Promise<CaptureVitalsResponse> => {
    const response = await apiClient.post<CaptureVitalsResponse>(
      `/visits/${visitId}/vitals`,
      data,
    );
    return response.data;
  },

  /** Edicion auditada de una captura YA existente (Fase 3, D8). NO crea
   * fila nueva, NO avanza `status`, NO acepta reuso -- corrige la MISMA
   * fila. Requiere `motivo`; el backend responde 400 sin el, 404
   * `VITALS_NOT_FOUND` si la visita nunca tuvo captura, 403 sin la
   * capability `flow.somatometria.edit`. */
  editVitals: async (
    visitId: number,
    data: EditVitalsRequest,
  ): Promise<EditVitalsResponse> => {
    const response = await apiClient.patch<EditVitalsResponse>(
      `/visits/${visitId}/vitals`,
      data,
    );
    return response.data;
  },

  /** Ultima captura de vitales del paciente de esta visita, para precargar
   * el formulario -- `vitals: null` si el paciente nunca tuvo una previa. */
  getLatestVitals: async (visitId: number): Promise<LatestVitalsResponse> => {
    const response = await apiClient.get<LatestVitalsResponse>(
      `/visits/${visitId}/vitals`,
    );
    return response.data;
  },

  saveDiagnosis: async (
    visitId: number,
    data: SaveDiagnosisRequest,
  ): Promise<SaveDiagnosisResponse> => {
    const response = await apiClient.post<SaveDiagnosisResponse>(
      `/visits/${visitId}/diagnosis`,
      data,
    );
    return response.data;
  },

  searchCies: async (params: CieSearchParams): Promise<CieSearchResponse> => {
    const response = await apiClient.get<CieSearchResponse>(
      "/visits/cies/search",
      {
        params,
      },
    );
    return response.data;
  },

  getSecondaryDiagnoses: async (
    visitId: number,
  ): Promise<VisitSecondaryDiagnosesResponse> => {
    const response = await apiClient.get<VisitSecondaryDiagnosesResponse>(
      `/visits/${visitId}/diagnoses`,
    );
    return response.data;
  },

  addSecondaryDiagnosis: async (
    visitId: number,
    data: AddSecondaryDiagnosisRequest,
  ): Promise<SecondaryDiagnosisItem> => {
    const response = await apiClient.post<SecondaryDiagnosisItem>(
      `/visits/${visitId}/diagnoses`,
      data,
    );
    return response.data;
  },

  cancelSecondaryDiagnosis: async (
    visitId: number,
    diagnosisId: number,
  ): Promise<SecondaryDiagnosisItem> => {
    const response = await apiClient.patch<SecondaryDiagnosisItem>(
      `/visits/${visitId}/diagnoses/${diagnosisId}/cancel`,
    );
    return response.data;
  },

  getPrescriptionItems: async (
    visitId: number,
  ): Promise<VisitPrescriptionItemsResponse> => {
    const response = await apiClient.get<VisitPrescriptionItemsResponse>(
      `/visits/${visitId}/prescription-items`,
    );
    return response.data;
  },

  addPrescriptionItem: async (
    visitId: number,
    data: AddPrescriptionItemRequest,
  ): Promise<AddPrescriptionItemResult> => {
    const response = await apiClient.post<AddPrescriptionItemResult>(
      `/visits/${visitId}/prescription-items`,
      data,
    );
    return response.data;
  },

  cancelPrescriptionItem: async (
    visitId: number,
    itemId: number,
  ): Promise<PrescriptionItem> => {
    const response = await apiClient.patch<PrescriptionItem>(
      `/visits/${visitId}/prescription-items/${itemId}/cancel`,
    );
    return response.data;
  },

  savePrescriptions: async (
    visitId: number,
    data: SavePrescriptionRequest,
  ): Promise<SavePrescriptionResponse> => {
    const response = await apiClient.post<SavePrescriptionResponse>(
      `/visits/${visitId}/prescriptions`,
      data,
    );
    return response.data;
  },

  startConsultation: async (
    visitId: number,
  ): Promise<StartConsultationResponse> => {
    const response = await apiClient.post<StartConsultationResponse>(
      `/visits/${visitId}/consultation/start`,
      {},
    );
    return response.data;
  },

  closeVisit: async (
    visitId: number,
    data: CloseVisitRequest,
  ): Promise<CloseVisitResponse> => {
    const response = await apiClient.post<CloseVisitResponse>(
      `/visits/${visitId}/consultation/close`,
      data,
    );
    return response.data;
  },

  patientLookup: async (noExp: string, historico = false): Promise<PatientLookupResponse> => {
    const response = await apiClient.get<PatientLookupResponse>(
      "/visits/patient-lookup",
      { params: { noExp, ...(historico ? { historico: "true" } : {}) } },
    );
    return response.data;
  },

  downloadFicha: async (visitId: number): Promise<Blob> => {
    const response = await apiClient.get(`/visits/${visitId}/ficha`, {
      responseType: "blob",
    });
    return response.data as Blob;
  },

  getStatusLog: async (visitId: number): Promise<VisitStatusLogResponse> => {
    const response = await apiClient.get<VisitStatusLogResponse>(
      `/visits/${visitId}/status-log`,
    );
    return response.data;
  },
};
