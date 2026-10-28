import apiClient from "@api/client";
import type {
  AmbitoMotivo,
  ListaResponse,
  MotivoAltaRequest,
  MotivoConfiguracion,
  MotivoEdicionRequest,
  ReglaCentro,
  ReglaCentroAltaRequest,
  ReglaCentroEdicionRequest,
  TipoConfiguracion,
  TipoEdicionRequest,
} from "@api/types/autorizaciones/configuracion.types";

const BASE = "/autorizaciones/configuracion";

export const configuracionAutorizacionesAPI = {
  getTipos: async (): Promise<ListaResponse<TipoConfiguracion>> =>
    (await apiClient.get<ListaResponse<TipoConfiguracion>>(`${BASE}/tipos/`)).data,

  updateTipo: async (id: number, data: TipoEdicionRequest): Promise<{ tipo: TipoConfiguracion }> =>
    (await apiClient.patch<{ tipo: TipoConfiguracion }>(`${BASE}/tipos/${id}/`, data)).data,

  getReglas: async (): Promise<ListaResponse<ReglaCentro>> =>
    (await apiClient.get<ListaResponse<ReglaCentro>>(`${BASE}/reglas/`)).data,

  createRegla: async (data: ReglaCentroAltaRequest): Promise<{ regla: ReglaCentro }> =>
    (await apiClient.post<{ regla: ReglaCentro }>(`${BASE}/reglas/`, data)).data,

  updateRegla: async (id: number, data: ReglaCentroEdicionRequest): Promise<{ regla: ReglaCentro }> =>
    (await apiClient.patch<{ regla: ReglaCentro }>(`${BASE}/reglas/${id}/`, data)).data,

  bajaRegla: async (id: number, version: number): Promise<{ regla: ReglaCentro }> =>
    (await apiClient.post<{ regla: ReglaCentro }>(`${BASE}/reglas/${id}/baja/`, { version })).data,

  getMotivos: async (ambito?: AmbitoMotivo): Promise<ListaResponse<MotivoConfiguracion>> =>
    (await apiClient.get<ListaResponse<MotivoConfiguracion>>(`${BASE}/motivos/`, { params: { ambito } })).data,

  createMotivo: async (data: MotivoAltaRequest): Promise<{ motivo: MotivoConfiguracion }> =>
    (await apiClient.post<{ motivo: MotivoConfiguracion }>(`${BASE}/motivos/`, data)).data,

  updateMotivo: async (id: number, data: MotivoEdicionRequest): Promise<{ motivo: MotivoConfiguracion }> =>
    (await apiClient.patch<{ motivo: MotivoConfiguracion }>(`${BASE}/motivos/${id}/`, data)).data,
};
