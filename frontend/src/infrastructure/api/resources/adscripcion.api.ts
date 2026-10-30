import apiClient from "@api/client";
import type {
  AdscribirRequest,
  AdscribirResponse,
  AdscripcionPacienteResponse,
  CitaAfectada,
  CitasPorReagendarParams,
  CitasPorReagendarResponse,
  ConsultorioFamiliar,
  ConsultorioFamiliarCreateRequest,
  ConsultorioFamiliarUpdateRequest,
  EquivalenciaClinica,
  EquivalenciaClinicaCreateRequest,
  EquivalenciaClinicaUpdateRequest,
  HistorialAdscripcionResponse,
  ListaResponse,
  OpcionesAdscripcionResponse,
  PrevisualizarAdscripcionRequest,
  PrevisualizarAdscripcionResponse,
} from "@api/types";

/** P-03 · Adscripción a consultorio familiar. */
export const adscripcionAPI = {
  getPaciente: async (idPaciente: number): Promise<AdscripcionPacienteResponse> => {
    const r = await apiClient.get<AdscripcionPacienteResponse>(`/adscripcion/pacientes/${idPaciente}`);
    return r.data;
  },

  getOpciones: async (idPaciente: number, turnoId?: number): Promise<OpcionesAdscripcionResponse> => {
    const r = await apiClient.get<OpcionesAdscripcionResponse>("/adscripcion/opciones", {
      params: { idPaciente, ...(turnoId ? { turnoId } : {}) },
    });
    return r.data;
  },

  previsualizar: async (data: PrevisualizarAdscripcionRequest): Promise<PrevisualizarAdscripcionResponse> => {
    const r = await apiClient.post<PrevisualizarAdscripcionResponse>("/adscripcion/previsualizar", data);
    return r.data;
  },

  adscribir: async (data: AdscribirRequest): Promise<AdscribirResponse> => {
    const r = await apiClient.post<AdscribirResponse>("/adscripcion", data);
    return r.data;
  },

  getHistorial: async (idPaciente: number): Promise<HistorialAdscripcionResponse> => {
    const r = await apiClient.get<HistorialAdscripcionResponse>(`/adscripcion/pacientes/${idPaciente}/historial`);
    return r.data;
  },

  getCitasPorReagendar: async (params: CitasPorReagendarParams): Promise<CitasPorReagendarResponse> => {
    const r = await apiClient.get<CitasPorReagendarResponse>("/adscripcion/citas-por-reagendar", { params });
    return r.data;
  },

  descartarCitaAfectada: async (idCitaAfectada: number, motivo: string): Promise<CitaAfectada> => {
    const r = await apiClient.post<CitaAfectada>(
      `/adscripcion/citas-por-reagendar/${idCitaAfectada}/descartar`,
      { motivo },
    );
    return r.data;
  },

  // ── Configuración (administrador) ──────────────────────────────────────────

  getEquivalencias: async (): Promise<ListaResponse<EquivalenciaClinica>> => {
    const r = await apiClient.get<ListaResponse<EquivalenciaClinica>>("/adscripcion/config/clinicas");
    return r.data;
  },

  crearEquivalencia: async (data: EquivalenciaClinicaCreateRequest): Promise<EquivalenciaClinica> => {
    const r = await apiClient.post<EquivalenciaClinica>("/adscripcion/config/clinicas", data);
    return r.data;
  },

  actualizarEquivalencia: async (
    id: number,
    data: EquivalenciaClinicaUpdateRequest,
  ): Promise<EquivalenciaClinica> => {
    const r = await apiClient.patch<EquivalenciaClinica>(`/adscripcion/config/clinicas/${id}`, data);
    return r.data;
  },

  getConsultoriosFamiliares: async (centroId?: number): Promise<ListaResponse<ConsultorioFamiliar>> => {
    const r = await apiClient.get<ListaResponse<ConsultorioFamiliar>>("/adscripcion/config/consultorios", {
      params: centroId ? { centroId } : {},
    });
    return r.data;
  },

  crearConsultorioFamiliar: async (data: ConsultorioFamiliarCreateRequest): Promise<ConsultorioFamiliar> => {
    const r = await apiClient.post<ConsultorioFamiliar>("/adscripcion/config/consultorios", data);
    return r.data;
  },

  actualizarConsultorioFamiliar: async (
    id: number,
    data: ConsultorioFamiliarUpdateRequest,
  ): Promise<ConsultorioFamiliar> => {
    const r = await apiClient.patch<ConsultorioFamiliar>(`/adscripcion/config/consultorios/${id}`, data);
    return r.data;
  },
};
