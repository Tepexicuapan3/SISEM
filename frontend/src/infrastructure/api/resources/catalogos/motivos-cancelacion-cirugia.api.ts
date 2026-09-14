import apiClient from "@api/client";
import type {
  MotivoCancelacionCirugiaListParams,
  MotivoCancelacionCirugiaListResponse,
  MotivoCancelacionCirugiaDetailResponse,
  CreateMotivoCancelacionCirugiaRequest,
  CreateMotivoCancelacionCirugiaResponse,
  UpdateMotivoCancelacionCirugiaRequest,
  UpdateMotivoCancelacionCirugiaResponse,
  DeleteMotivoCancelacionCirugiaResponse,
} from "@api/types";

export const motivoCancelacionCirugiaAPI = {
  getAll: async (params?: MotivoCancelacionCirugiaListParams): Promise<MotivoCancelacionCirugiaListResponse> => {
    const response = await apiClient.get<MotivoCancelacionCirugiaListResponse>("/surgery-cancellation-reasons/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<MotivoCancelacionCirugiaDetailResponse> => {
    const response = await apiClient.get<MotivoCancelacionCirugiaDetailResponse>(`/surgery-cancellation-reasons/${id}/`);
    return response.data;
  },
  create: async (data: CreateMotivoCancelacionCirugiaRequest): Promise<CreateMotivoCancelacionCirugiaResponse> => {
    const response = await apiClient.post<CreateMotivoCancelacionCirugiaResponse>("/surgery-cancellation-reasons/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateMotivoCancelacionCirugiaRequest): Promise<UpdateMotivoCancelacionCirugiaResponse> => {
    const response = await apiClient.put<UpdateMotivoCancelacionCirugiaResponse>(`/surgery-cancellation-reasons/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteMotivoCancelacionCirugiaResponse> => {
    const response = await apiClient.delete<DeleteMotivoCancelacionCirugiaResponse>(`/surgery-cancellation-reasons/${id}/`);
    return response.data;
  },
};
