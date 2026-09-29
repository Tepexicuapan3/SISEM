import apiClient from "@api/client";
import type { AccessLogListParams, AccessLogListResponse } from "@api/types";

export const accessLogAPI = {
  getList: async (params: AccessLogListParams): Promise<AccessLogListResponse> => {
    const response = await apiClient.get<AccessLogListResponse>("/bitacora-acceso", { params });
    return response.data;
  },
};
