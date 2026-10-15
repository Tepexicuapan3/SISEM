import apiClient from "@api/client";
import type {
  MotivoCancelacionNotaListParams,
  MotivoCancelacionNotaListResponse,
  MotivoCancelacionNotaDetailResponse,
  CreateMotivoCancelacionNotaRequest,
  CreateMotivoCancelacionNotaResponse,
  UpdateMotivoCancelacionNotaRequest,
  UpdateMotivoCancelacionNotaResponse,
  DeleteMotivoCancelacionNotaResponse,
} from "@api/types";

export const motivoCancelacionNotaAPI = {
  getAll: async (params?: MotivoCancelacionNotaListParams): Promise<MotivoCancelacionNotaListResponse> => {
    const response = await apiClient.get<MotivoCancelacionNotaListResponse>("/note-cancellation-reasons/", { params });
    return response.data;
  },
  getById: async (id: number): Promise<MotivoCancelacionNotaDetailResponse> => {
    const response = await apiClient.get<MotivoCancelacionNotaDetailResponse>(`/note-cancellation-reasons/${id}/`);
    return response.data;
  },
  create: async (data: CreateMotivoCancelacionNotaRequest): Promise<CreateMotivoCancelacionNotaResponse> => {
    const response = await apiClient.post<CreateMotivoCancelacionNotaResponse>("/note-cancellation-reasons/", data);
    return response.data;
  },
  update: async (id: number, data: UpdateMotivoCancelacionNotaRequest): Promise<UpdateMotivoCancelacionNotaResponse> => {
    const response = await apiClient.put<UpdateMotivoCancelacionNotaResponse>(`/note-cancellation-reasons/${id}/`, data);
    return response.data;
  },
  delete: async (id: number): Promise<DeleteMotivoCancelacionNotaResponse> => {
    const response = await apiClient.delete<DeleteMotivoCancelacionNotaResponse>(`/note-cancellation-reasons/${id}/`);
    return response.data;
  },
};
