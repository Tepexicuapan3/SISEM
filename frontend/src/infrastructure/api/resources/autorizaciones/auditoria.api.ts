import apiClient from "@api/client";
import type {
  AuditoriaLineaDeTiempo,
  AuditoriaListResponse,
  AuditoriaParams,
} from "@api/types/autorizaciones/auditoria.types";

const BASE = "/autorizaciones/auditoria/solicitudes";

export const auditoriaAutorizacionesAPI = {
  getAll: async (params?: AuditoriaParams): Promise<AuditoriaListResponse> =>
    (await apiClient.get<AuditoriaListResponse>(`${BASE}/`, { params })).data,

  getLineaDeTiempo: async (uuid: string): Promise<AuditoriaLineaDeTiempo> =>
    (await apiClient.get<AuditoriaLineaDeTiempo>(`${BASE}/${uuid}/`)).data,

  /** Excel de lo filtrado (maximo 5,000 filas); el backend lo registra en la bitacora. */
  exportXlsx: async (params?: Omit<AuditoriaParams, "page" | "pageSize">): Promise<Blob> => {
    const response = await apiClient.get(`${BASE}/`, { params: { ...params, export: "xlsx" }, responseType: "blob" });
    return response.data as Blob;
  },
};
