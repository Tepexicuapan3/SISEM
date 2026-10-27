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

// ── Recien nacidos provisionales (plan identidad, bloque C1) ──────────────

/** Familiar de SERMED que podria ser el recien nacido (misma fecha y sexo). */
export interface CandidatoSermed {
  pkNum: number;
  nombre: string;
  fechaNacimiento: string | null;
  sexo: "M" | "F" | "X" | null;
  parentesco: string | null;
  /** SIRES ya le habia abierto registro (se vincula igual, sin mover nada). */
  yaTieneRegistro: boolean;
}

export interface RecienNacidoProvisional {
  idPaciente: number;
  cdProvisional: number;
  nombre: string;
  fechaNacimiento: string | null;
  sexo: "M" | "F" | "X" | null;
  curp: string | null;
  madre: string | null;
  orden: number;
  /** A = provisional, B = vinculado a SERMED. */
  estatus: "A" | "B";
  clinica: string | null;
  vigencia: string;
  vigente: boolean;
  pkNumSermed: number | null;
  candidatos: CandidatoSermed[];
}

export interface RecienNacidosResponse {
  /** Interruptor IDENTIDAD_RECIEN_NACIDOS: apagado, la seccion no se muestra. */
  habilitado: boolean;
  provisionales: RecienNacidoProvisional[];
  /** Propuesta desde SERMED: la titular, o su unica esposa/concubina vigente. */
  madreSugerida: string | null;
  /** La titular es la madre: mostrar el nombre de la madre seria redundante. */
  titularEsMujer: boolean;
}

export interface RegistrarRecienNacidoRequest {
  paternalSurname: string;
  maternalSurname: string;
  firstName: string;
  birthDate: string;
  sex: "M" | "F" | "X";
  motherName?: string;
  birthOrder?: number;
  curp?: string;
  /** SERMED ya tiene un hijo con esa fecha y sexo y aun asi es otro bebe (p. ej. gemelos). */
  confirmarAunqueExista?: boolean;
}

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