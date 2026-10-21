export interface EmpleadoExpediente {
  NO_EXP: string;
  DS_PATERNO: string | null;
  DS_MATERNO: string | null;
  DS_NOMBRE: string | null;
  CD_LABORAL: string | null;
  CVE_BAJA: string | null;
  FEC_BAJA: string | null;
  FE_NAC: string | null;
  FEC_VIG: string | null;
  PARENTESCO: string;
  CLINICA: string | null;
  ESTATUS: 'ACTIVO' | 'BAJA';
  EDAD: number | null;
  FOTO: string | null;
}

export interface FamiliarExpediente {
  NO_EXPF: string;
  PK_NUM: number;
  DS_PATERNO: string | null;
  DS_MATERNO: string | null;
  DS_NOMBRE: string | null;
  CD_PARENTESCO: string | null;
  FE_NAC: string | null;
  FEC_VIG: string | null;
  CLINICA: string | null;
  ESTATUS: 'ACTIVO' | 'NO ACTIVO';
  EDAD: number | null;
  FOTO: string | null;
}

/** Última actualización que dejó la réplica de SERMED al día (bitacora_sync_expediente). */
export interface UltimaActualizacionExpediente {
  id_sync: number;
  fecha: string;
  usuario: string;
  resultado: 'OK' | 'PARCIAL';
}

export interface ExpedienteResponse {
  empleados: EmpleadoExpediente[];
  familiares: FamiliarExpediente[];
  ultima_actualizacion: UltimaActualizacionExpediente | null;
}

export interface EmpleadoResumen {
  NO_EXP: string | number;
  DS_PATERNO: string | null;
  DS_MATERNO: string | null;
  DS_NOMBRE: string | null;
  CD_LABORAL: string | null;
  CVE_CD_LABORAL: string | null;
  FEC_BAJA: string | null;
  FEC_VIG: string | null;
  CLINICA: string | null;
  ESTATUS: 'ACTIVO' | 'BAJA';
}

export type BuscarPorNombreResponse = EmpleadoResumen[];

export interface ActualizarExpedienteRequest {
  expediente: string;
}

export interface SyncConteos {
  insertados: number;
  eliminados: number;
  actualizados: number;
}

/**
 * OK: réplica y pacientes al día. PARCIAL: la réplica se actualizó pero los
 * pacientes de SIRES no (ver `errores`). ERROR (502, code SYNC_ERROR) y
 * OCUPADO (409, code SYNC_EN_CURSO) llegan como ApiError.
 */
export type EstadoSyncExpediente = 'OK' | 'PARCIAL';

export interface ActualizarExpedienteResponse {
  estado: EstadoSyncExpediente;
  id_sync: number;
  tablas: Record<string, SyncConteos>;
  cambios_registrados?: number;
  pacientes?: Record<string, number>;
  errores: string[];
}