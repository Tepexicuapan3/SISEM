import apiClient from "@api/client";
import { conIdPaciente } from "@api/paciente-ids";
import type {
  BuscarDerechohabienteParams,
  BuscarDerechohabienteResponse,
  ContratoOxigeno,
  ContratosListParams,
  ContratosListResponse,
  ContratosStats,
  CreateContratoRequest,
  NotificarRequest,
  NotificarResponse,
  UpdateContratoRequest,
} from "@api/types";

export const contratosAPI = {
  getAll: async (params?: ContratosListParams): Promise<ContratosListResponse> => {
    const response = await apiClient.get<ContratosListResponse>("/contratos-oxigeno/", { params });
    return response.data;
  },

  getById: async (id: number): Promise<ContratoOxigeno> => {
    const response = await apiClient.get<ContratoOxigeno>(`/contratos-oxigeno/${id}/`);
    return response.data;
  },

  create: async (data: CreateContratoRequest): Promise<ContratoOxigeno> => {
    const response = await apiClient.post<ContratoOxigeno>("/contratos-oxigeno/", await conIdPaciente(data, "expediente"));
    return response.data;
  },

  update: async (id: number, data: UpdateContratoRequest): Promise<ContratoOxigeno> => {
    const response = await apiClient.patch<ContratoOxigeno>(`/contratos-oxigeno/${id}/`, data);
    return response.data;
  },

  getStats: async (): Promise<ContratosStats> => {
    const response = await apiClient.get<ContratosStats>("/contratos-oxigeno/estadisticas/");
    return response.data;
  },

  descargarFormato: async (id: number): Promise<Blob> => {
    const response = await apiClient.get(`/contratos-oxigeno/${id}/formato/`, {
      responseType: "blob",
    });
    return response.data as Blob;
  },

  buscarDerechohabiente: async (params: BuscarDerechohabienteParams): Promise<BuscarDerechohabienteResponse> => {
    const response = await apiClient.get<BuscarDerechohabienteResponse>("/contratos-oxigeno/buscar-derechohabiente/", { params });
    return response.data;
  },

  notificar: async (
    payload: NotificarRequest,
    adjuntos?: File[],
  ): Promise<NotificarResponse> => {
    if (adjuntos && adjuntos.length > 0) {
      const form = new FormData();
      form.append("destinatarios", JSON.stringify(payload.destinatarios));
      form.append("asunto", payload.asunto);
      if (payload.cuerpo)       form.append("cuerpo",       payload.cuerpo);
      if (payload.contratosIds) form.append("contratosIds", JSON.stringify(payload.contratosIds));
      adjuntos.forEach((f) => form.append("adjunto", f, f.name));
      const response = await apiClient.post<NotificarResponse>("/contratos-oxigeno/notificar/", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return response.data;
    }
    const response = await apiClient.post<NotificarResponse>("/contratos-oxigeno/notificar/", payload);
    return response.data;
  },
};
