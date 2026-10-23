import apiClient from '../client';
import type {
  ExpedienteResponse,
  ActualizarExpedienteRequest,
  ActualizarExpedienteResponse,
  BuscarPorNombreResponse,
  RecienNacidoProvisional,
  RecienNacidosResponse,
  RegistrarRecienNacidoRequest,
} from '../types/expedientes.types';

export const expedientesAPI = {
  buscar: async (idEmpleado: string): Promise<ExpedienteResponse> => {
    const res = await apiClient.get<ExpedienteResponse>(
      '/expedientes/',
      { params: { id_empleado: idEmpleado } },
    );
    return res.data;
  },

  buscarPorNombre: async (nombre: string): Promise<BuscarPorNombreResponse> => {
    const res = await apiClient.get<BuscarPorNombreResponse>(
      '/expedientes/buscar-nombre/',
      { params: { nombre } },
    );
    return res.data;
  },

  actualizar: async (
    data: ActualizarExpedienteRequest,
  ): Promise<ActualizarExpedienteResponse> => {
    const res = await apiClient.post<ActualizarExpedienteResponse>(
      '/expedientes/actualizar/',
      data,
    );
    return res.data;
  },

  // ── Recien nacidos provisionales (plan identidad, bloque C1) ────────────
  recienNacidos: async (noExp: string): Promise<RecienNacidosResponse> => {
    const res = await apiClient.get<RecienNacidosResponse>(
      `/expedientes/${encodeURIComponent(noExp)}/recien-nacidos/`,
    );
    return res.data;
  },

  registrarRecienNacido: async (
    noExp: string,
    data: RegistrarRecienNacidoRequest,
  ): Promise<RecienNacidoProvisional> => {
    const res = await apiClient.post<RecienNacidoProvisional>(
      `/expedientes/${encodeURIComponent(noExp)}/recien-nacidos/`,
      data,
    );
    return res.data;
  },

  vincularRecienNacido: async (idPaciente: number, pkNum: number): Promise<RecienNacidoProvisional> => {
    const res = await apiClient.post<RecienNacidoProvisional>(
      `/expedientes/recien-nacidos/${idPaciente}/vincular/`,
      { pkNum },
    );
    return res.data;
  },

  descartarCoincidencia: async (
    idPaciente: number,
    pkNum: number,
    motivo?: string,
  ): Promise<RecienNacidoProvisional> => {
    const res = await apiClient.post<RecienNacidoProvisional>(
      `/expedientes/recien-nacidos/${idPaciente}/descartar/`,
      { pkNum, motivo },
    );
    return res.data;
  },
};
