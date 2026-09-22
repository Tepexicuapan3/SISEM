/**
 * Dispensación de Farmacia API Resource (sdd/dispensacion-farmacia)
 *
 * Endpoints (apps.consulta_medica):
 * - GET  /prescriptions/dispensations/pending?idAlmacen=
 * - GET  /prescriptions/:id/dispensation
 * - POST /prescriptions/:id/dispense
 */

import apiClient from "@api/client";
import type {
  DispensationPreviewResponse,
  DispensationQueueParams,
  DispensationQueueResponse,
  DispensePrescriptionRequest,
  DispensePrescriptionResponse,
} from "@api/types/farmacia/dispensacion.types";

export const dispensacionFarmaciaAPI = {
  getPendingQueue: async (params?: DispensationQueueParams): Promise<DispensationQueueResponse> => {
    const response = await apiClient.get<DispensationQueueResponse>(
      "/prescriptions/dispensations/pending",
      { params },
    );
    return response.data;
  },

  getPreview: async (prescriptionId: number): Promise<DispensationPreviewResponse> => {
    const response = await apiClient.get<DispensationPreviewResponse>(
      `/prescriptions/${prescriptionId}/dispensation`,
    );
    return response.data;
  },

  dispense: async (
    prescriptionId: number,
    data: DispensePrescriptionRequest,
  ): Promise<DispensePrescriptionResponse> => {
    const response = await apiClient.post<DispensePrescriptionResponse>(
      `/prescriptions/${prescriptionId}/dispense`,
      data,
    );
    return response.data;
  },
};
