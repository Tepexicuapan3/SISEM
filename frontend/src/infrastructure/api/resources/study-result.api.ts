/**
 * NOTA SOBRE UPLOAD Y FORMDATA: mismo patrón que
 * `comunicados/anuncios.api.ts` — el interceptor global no puede reenviar
 * un FormData ya consumido en un retry de 401, así que create() reintenta
 * por su cuenta después de esperar el refresh del token.
 */

import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  CreateStudyResultRequest,
  PatientStudyResultsResponse,
  StudyResultItem,
} from "@api/types/study-result.types";

interface ApiErrorWithStatus {
  status?: number;
}

const waitForTokenRefresh = (): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, 800));

const hasStatus = (error: unknown): error is ApiErrorWithStatus =>
  typeof error === "object" && error !== null && "status" in error;

const multipartHeaders = {
  // Elimina Content-Type: application/json del cliente base.
  // Axios genera multipart/form-data con boundary correcto.
  "Content-Type": undefined,
};

const buildStudyResultFormData = (data: CreateStudyResultRequest): FormData => {
  const formData = new FormData();
  formData.append("studyTypeId", String(data.studyTypeId));
  formData.append("resultDate", data.resultDate);
  if (data.notes) formData.append("notes", data.notes);
  formData.append("file", data.file);
  return formData;
};

export const studyResultAPI = {
  getPatientHistory: async (
    noExp: string,
    pkNum = 0,
  ): Promise<PatientStudyResultsResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `study-results`);
    const response = await apiClient.get<PatientStudyResultsResponse>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },

  create: async (
    visitId: number,
    data: CreateStudyResultRequest,
    _retry = false,
  ): Promise<StudyResultItem> => {
    try {
      const response = await apiClient.post<StudyResultItem>(
        `/visits/${visitId}/study-results`,
        buildStudyResultFormData(data),
        { headers: multipartHeaders },
      );
      return response.data;
    } catch (err: unknown) {
      if (!_retry && hasStatus(err) && err.status === 401) {
        await waitForTokenRefresh();
        return studyResultAPI.create(visitId, data, true);
      }
      throw err;
    }
  },
};
