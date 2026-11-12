import apiClient from "@api/client";
import type {
  CreateMedicamentoRequest,
  CreateMedicamentoResponse,
  DeleteMedicamentoResponse,
  MedicamentoDetailResponse,
  MedicamentosListParams,
  MedicamentosListResponse,
  UpdateMedicamentoRequest,
  UpdateMedicamentoResponse,
} from "@api/types/catalogos/medicamentos.types";

export const medicamentosAPI = {
  getAll: async (
    params?: MedicamentosListParams,
  ): Promise<MedicamentosListResponse> => {
    const response = await apiClient.get<MedicamentosListResponse>(
      "/medications/",
      { params },
    );
    return response.data;
  },

  getById: async (id: number): Promise<MedicamentoDetailResponse> => {
    const response = await apiClient.get<MedicamentoDetailResponse>(`/medications/${id}/`);
    return response.data;
  },

  create: async (data: CreateMedicamentoRequest): Promise<CreateMedicamentoResponse> => {
    const response = await apiClient.post<CreateMedicamentoResponse>("/medications/", data);
    return response.data;
  },

  update: async (id: number, data: UpdateMedicamentoRequest): Promise<UpdateMedicamentoResponse> => {
    const response = await apiClient.put<UpdateMedicamentoResponse>(`/medications/${id}/`, data);
    return response.data;
  },

  delete: async (id: number): Promise<DeleteMedicamentoResponse> => {
    const response = await apiClient.delete<DeleteMedicamentoResponse>(`/medications/${id}/`);
    return response.data;
  },
};
