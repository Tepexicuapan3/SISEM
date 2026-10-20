import apiClient from "@api/client";
import type {
  MedicosListResponse,
  LegacyMedicosListResponse,
  LegacyMedicosParams,
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
  CreateExcepcionResponse,
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

  /** Archivo legado (solo lectura), paginado en servidor. */
  getLegacy: async (params?: LegacyMedicosParams): Promise<LegacyMedicosListResponse> => {
    const r = await apiClient.get<LegacyMedicosListResponse>("/medicos/legado", { params });
    return r.data;
  },

  create: async (data: CreateMedicoRequest): Promise<MedicoListItem> => {
    const r = await apiClient.post<MedicoListItem>("/medicos", data);
    return r.data;
  },

  getById: async (medicoId: number): Promise<MedicoDetailResponse> => {
    const r = await apiClient.get<MedicoDetailResponse>(`/medicos/${medicoId}`);
    return r.data;
  },

  update: async (medicoId: number, data: UpdateMedicoRequest): Promise<MedicoDetail> => {
    const r = await apiClient.patch<MedicoDetail>(`/medicos/${medicoId}`, data);
    return r.data;
  },

  // ── Especialidades ────────────────────────────────────────────────────────

  addEspecialidad: async (medicoId: number, data: AddEspecialidadRequest) => {
    const r = await apiClient.post(`/medicos/${medicoId}/especialidades`, data);
    return r.data;
  },

  removeEspecialidad: async (medicoId: number, especialidadId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/especialidades/${especialidadId}`);
    return r.data;
  },

  // ── Centros ───────────────────────────────────────────────────────────────

  addCentro: async (medicoId: number, data: AddCentroRequest) => {
    const r = await apiClient.post(`/medicos/${medicoId}/centros`, data);
    return r.data;
  },

  removeCentro: async (medicoId: number, relId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/centros/${relId}`);
    return r.data;
  },

  // ── Consultorios ──────────────────────────────────────────────────────────

  addConsultorio: async (medicoId: number, data: AddConsultorioRequest) => {
    const r = await apiClient.post(`/medicos/${medicoId}/consultorios`, data);
    return r.data;
  },

  updateConsultorio: async (medicoId: number, rmcId: number, data: { consultorioId?: number; tipoAsignacion?: string }) => {
    const r = await apiClient.patch(`/medicos/${medicoId}/consultorios/${rmcId}`, data);
    return r.data;
  },

  removeConsultorio: async (medicoId: number, rmcId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/consultorios/${rmcId}`);
    return r.data;
  },

  saveHorario: async (medicoId: number, rmcId: number, data: SaveHorarioRequest) => {
    const r = await apiClient.put(`/medicos/${medicoId}/consultorios/${rmcId}/horario`, data);
    return r.data;
  },

  // ── Excepciones ───────────────────────────────────────────────────────────

  getExcepciones: async (medicoId: number): Promise<MedicoExcepcionesResponse> => {
    const r = await apiClient.get<MedicoExcepcionesResponse>(`/medicos/${medicoId}/excepciones`);
    return r.data;
  },

  createExcepcion: async (
    medicoId: number,
    data: CreateExcepcionRequest,
  ): Promise<CreateExcepcionResponse> => {
    const r = await apiClient.post<CreateExcepcionResponse>(`/medicos/${medicoId}/excepciones`, data);
    return r.data;
  },

  deleteExcepcion: async (medicoId: number, excId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/excepciones/${excId}`);
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

  getDisponibilidad: async (medicoId: number, fecha?: string): Promise<MedicoDisponible> => {
    const r = await apiClient.get<MedicoDisponible>(`/medicos/${medicoId}/disponibilidad`, {
      params: { fecha },
    });
    return r.data;
  },
};
