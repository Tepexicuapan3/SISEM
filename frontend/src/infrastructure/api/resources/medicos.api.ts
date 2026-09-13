import apiClient from "@api/client";
import type {
  MedicosListResponse,
  MedicoDetailResponse,
  MedicoListItem,
  MedicoDetail,
  CreateMedicoRequest,
  UpdateMedicoRequest,
  AddEspecialidadRequest,
  AddCentroRequest,
  AddConsultorioRequest,
  SaveHorarioRequest,
  CreateExcepcionRequest,
  CreateCoberturaRequest,
  MedicoExcepcionesResponse,
  MedicoCoberturaItem,
  MedicoCoberturasResponse,
  MedicosDisponiblesResponse,
  MedicoDisponible,
} from "@api/types/medicos.types";

export const medicosAPI = {
  // ── Catálogo ──────────────────────────────────────────────────────────────

  getAll: async (params?: {
    tipoMedico?: string;
    estatusMedico?: string;
    search?: string;
  }): Promise<MedicosListResponse> => {
    const r = await apiClient.get<MedicosListResponse>("/medicos", { params });
    return r.data;
  },

  create: async (data: CreateMedicoRequest): Promise<MedicoListItem> => {
    const r = await apiClient.post<MedicoListItem>("/medicos", data);
    return r.data;
  },

  getById: async (userId: number): Promise<MedicoDetailResponse> => {
    const r = await apiClient.get<MedicoDetailResponse>(`/medicos/${userId}`);
    return r.data;
  },

  update: async (userId: number, data: UpdateMedicoRequest): Promise<MedicoDetail> => {
    const r = await apiClient.patch<MedicoDetail>(`/medicos/${userId}`, data);
    return r.data;
  },

  // ── Especialidades ────────────────────────────────────────────────────────

  addEspecialidad: async (userId: number, data: AddEspecialidadRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/especialidades`, data);
    return r.data;
  },

  removeEspecialidad: async (userId: number, especialidadId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/especialidades/${especialidadId}`);
    return r.data;
  },

  // ── Centros ───────────────────────────────────────────────────────────────

  addCentro: async (userId: number, data: AddCentroRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/centros`, data);
    return r.data;
  },

  removeCentro: async (userId: number, relId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/centros/${relId}`);
    return r.data;
  },

  // ── Consultorios ──────────────────────────────────────────────────────────

  addConsultorio: async (userId: number, data: AddConsultorioRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/consultorios`, data);
    return r.data;
  },

  updateConsultorio: async (userId: number, rmcId: number, data: { consultorioId?: number; tipoAsignacion?: string }) => {
    const r = await apiClient.patch(`/medicos/${userId}/consultorios/${rmcId}`, data);
    return r.data;
  },

  removeConsultorio: async (userId: number, rmcId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/consultorios/${rmcId}`);
    return r.data;
  },

  saveHorario: async (userId: number, rmcId: number, data: SaveHorarioRequest) => {
    const r = await apiClient.put(`/medicos/${userId}/consultorios/${rmcId}/horario`, data);
    return r.data;
  },

  // ── Excepciones ───────────────────────────────────────────────────────────

  getExcepciones: async (userId: number): Promise<MedicoExcepcionesResponse> => {
    const r = await apiClient.get<MedicoExcepcionesResponse>(`/medicos/${userId}/excepciones`);
    return r.data;
  },

  createExcepcion: async (userId: number, data: CreateExcepcionRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/excepciones`, data);
    return r.data;
  },

  deleteExcepcion: async (userId: number, excId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/excepciones/${excId}`);
    return r.data;
  },

  // ── Coberturas ────────────────────────────────────────────────────────────

  createCobertura: async (data: CreateCoberturaRequest): Promise<MedicoCoberturaItem> => {
    const r = await apiClient.post<MedicoCoberturaItem>("/coberturas", data);
    return r.data;
  },

  getCoberturas: async (medicoId: number): Promise<MedicoCoberturasResponse> => {
    const r = await apiClient.get<MedicoCoberturasResponse>("/coberturas", {
      params: { medicoId },
    });
    return r.data;
  },

  deleteCobertura: async (coberturaId: number) => {
    const r = await apiClient.delete(`/coberturas/${coberturaId}`);
    return r.data;
  },

  // ── Disponibilidad (para recepción) ───────────────────────────────────────

  getDisponibles: async (centroId: number, fecha?: string): Promise<MedicosDisponiblesResponse> => {
    const r = await apiClient.get<MedicosDisponiblesResponse>("/medicos/disponibles", {
      params: { centroId, fecha },
    });
    return r.data;
  },

  getDisponibilidad: async (userId: number, fecha?: string): Promise<MedicoDisponible> => {
    const r = await apiClient.get<MedicoDisponible>(`/medicos/${userId}/disponibilidad`, {
      params: { fecha },
    });
    return r.data;
  },
};
