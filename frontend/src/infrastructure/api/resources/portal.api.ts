import portalClient from "@api/portalClient";
import type {
  PortalCancelarCitaRequest,
  PortalCancelarCitaResponse,
  PortalCapturarCorreoRequest,
  PortalCapturarCorreoResponse,
  PortalCentrosResponse,
  PortalCitasListResponse,
  PortalConsultoriosResponse,
  PortalDisponibilidadMensualResponse,
  PortalIdentidadRequest,
  PortalIniciarSesionResponse,
  PortalNucleoResponse,
  PortalReservarCitaRequest,
  PortalReservarCitaResponse,
  PortalSlotsResponse,
  PortalVerificarCodigoRequest,
  PortalVerificarCodigoResponse,
} from "@api/types/portal.types";

export const portalAuthAPI = {
  iniciarSesion: async (
    data: PortalIdentidadRequest,
  ): Promise<PortalIniciarSesionResponse> => {
    const r = await portalClient.post<PortalIniciarSesionResponse>(
      "/portal/auth/iniciar-sesion",
      data,
    );
    return r.data;
  },

  capturarCorreo: async (
    data: PortalCapturarCorreoRequest,
  ): Promise<PortalCapturarCorreoResponse> => {
    const r = await portalClient.post<PortalCapturarCorreoResponse>(
      "/portal/auth/capturar-correo",
      data,
    );
    return r.data;
  },

  verificarCodigo: async (
    data: PortalVerificarCodigoRequest,
  ): Promise<PortalVerificarCodigoResponse> => {
    const r = await portalClient.post<PortalVerificarCodigoResponse>(
      "/portal/auth/verificar-codigo",
      data,
    );
    return r.data;
  },
};

export const portalNucleoAPI = {
  get: async (): Promise<PortalNucleoResponse> => {
    const r = await portalClient.get<PortalNucleoResponse>("/portal/nucleo");
    return r.data;
  },
};

export const portalCitasAPI = {
  getAll: async (): Promise<PortalCitasListResponse> => {
    const r = await portalClient.get<PortalCitasListResponse>("/portal/citas");
    return r.data;
  },

  reservar: async (
    data: PortalReservarCitaRequest,
  ): Promise<PortalReservarCitaResponse> => {
    const r = await portalClient.post<PortalReservarCitaResponse>("/portal/citas", data);
    return r.data;
  },

  cancelar: async (
    folio: string,
    data: PortalCancelarCitaRequest,
  ): Promise<PortalCancelarCitaResponse> => {
    const r = await portalClient.patch<PortalCancelarCitaResponse>(
      `/portal/citas/${folio}/cancelar`,
      data,
    );
    return r.data;
  },
};

export const portalCatalogosAPI = {
  getCentros: async (): Promise<PortalCentrosResponse> => {
    const r = await portalClient.get<PortalCentrosResponse>("/portal/centros");
    return r.data;
  },

  getConsultorios: async (centroId?: number): Promise<PortalConsultoriosResponse> => {
    const r = await portalClient.get<PortalConsultoriosResponse>("/portal/consultorios", {
      params: centroId ? { centroId } : undefined,
    });
    return r.data;
  },

  getDisponibilidadMensual: async (
    consultorioId: number,
    anio: number,
    mes: number,
  ): Promise<PortalDisponibilidadMensualResponse> => {
    const r = await portalClient.get<PortalDisponibilidadMensualResponse>(
      `/portal/consultorios/${consultorioId}/disponibilidad-mensual`,
      { params: { anio, mes } },
    );
    return r.data;
  },

  getSlots: async (fecha: string, consultorioId: number): Promise<PortalSlotsResponse> => {
    const r = await portalClient.get<PortalSlotsResponse>("/portal/slots", {
      params: { fecha, consultorioId },
    });
    return r.data;
  },
};
