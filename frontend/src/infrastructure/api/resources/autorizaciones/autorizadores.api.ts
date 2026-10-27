import apiClient from "@api/client";
import type {
  AutorizadorAltaRequest,
  AutorizadorDetailResponse,
  AutorizadorEdicionRequest,
  AutorizadoresListParams,
  AutorizadoresListResponse,
  CambioEstatusRequest,
  CatalogosAutorizacionResponse,
  HistorialAutorizadorResponse,
  RenovacionRequest,
  UsuariosElegiblesResponse,
} from "@api/types/autorizaciones/autorizadores.types";

export type AccionEstatus = "suspender" | "reactivar" | "baja";

export const autorizadoresAPI = {
  getAll: async (params?: AutorizadoresListParams): Promise<AutorizadoresListResponse> => {
    const response = await apiClient.get<AutorizadoresListResponse>("/autorizadores/", { params });
    return response.data;
  },

  getById: async (id: number): Promise<AutorizadorDetailResponse> => {
    const response = await apiClient.get<AutorizadorDetailResponse>(`/autorizadores/${id}/`);
    return response.data;
  },

  create: async (data: AutorizadorAltaRequest): Promise<AutorizadorDetailResponse> => {
    const response = await apiClient.post<AutorizadorDetailResponse>("/autorizadores/", data);
    return response.data;
  },

  update: async (id: number, data: AutorizadorEdicionRequest): Promise<AutorizadorDetailResponse> => {
    const response = await apiClient.patch<AutorizadorDetailResponse>(`/autorizadores/${id}/`, data);
    return response.data;
  },

  cambiarEstatus: async (
    id: number,
    accion: AccionEstatus,
    data: CambioEstatusRequest | { version: number },
  ): Promise<AutorizadorDetailResponse> => {
    const response = await apiClient.post<AutorizadorDetailResponse>(
      `/autorizadores/${id}/${accion}/`,
      data,
    );
    return response.data;
  },

  renovar: async (id: number, data: RenovacionRequest): Promise<AutorizadorDetailResponse> => {
    const response = await apiClient.post<AutorizadorDetailResponse>(
      `/autorizadores/${id}/renovar/`,
      data,
    );
    return response.data;
  },

  getHistorial: async (id: number): Promise<HistorialAutorizadorResponse> => {
    const response = await apiClient.get<HistorialAutorizadorResponse>(
      `/autorizadores/${id}/historial/`,
    );
    return response.data;
  },

  getUsuariosElegibles: async (search?: string): Promise<UsuariosElegiblesResponse> => {
    const response = await apiClient.get<UsuariosElegiblesResponse>(
      "/autorizadores/usuarios-elegibles/",
      { params: { search } },
    );
    return response.data;
  },

  getCatalogos: async (): Promise<CatalogosAutorizacionResponse> => {
    const response = await apiClient.get<CatalogosAutorizacionResponse>("/autorizaciones/catalogos/");
    return response.data;
  },
};
