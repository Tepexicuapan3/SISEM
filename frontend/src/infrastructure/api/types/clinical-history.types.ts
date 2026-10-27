/**
 * Nucleo del paciente (documento "Historia Clinica Unificada", 5.1).
 */

/** H = Hombre, M = Mujer, X = No binario (mismas letras que el CURP). */
/** Convencion de SERMED: M = Masculino, F = Femenino, X = No binario. */
export type PatientSex = "M" | "F" | "X";

/** HISTORIA_CLINICA: cabecera unica del paciente (solo lectura). */
export interface ClinicalHistory {
  id: number;
  noExp: string;
  pkNum: number;
  patientId: number;
  openedOn: string | null;
  openingClinicCode: number | null;
  openingDoctorCode: string | null;
  /** De que fila del legado salio; null = abierta en SIRES. */
  legacySourceTable: "his_clinica" | "his_clinicad" | null;
  legacySourceId: number | null;
  isActive: boolean;
  createdAt: string;
}

/** Origen de la CURP: O = Capital Humano (SERMED, no editable), C = capturada en SIRES. */
export type CurpSource = "O" | "C";

/** PACIENTE: identidad y datos sociodemograficos (editable, versionado). */
export interface PatientProfile {
  id: number;
  /** Identificador estable para compartir con otras instituciones (NOM-024). */
  uuid: string;
  noExp: string;
  /** 0 = titular. null = familiar del legado sin PK_NUM (solo cd_familiar). */
  pkNum: number | null;
  legacyFamilyCode: number | null;
  provisionalCode: number | null;
  /** Copiados de SERMED en cada sincronizacion: solo lectura en SIRES. */
  paternalSurname: string | null;
  maternalSurname: string | null;
  firstName: string | null;
  birthDate: string | null;
  curp: string | null;
  curpSource: CurpSource | null;
  sex: PatientSex | null;
  occupationId: number | null;
  educationLevelId: number | null;
  maritalStatusId: number | null;
  religionId: number | null;
  residenceTypeId: number | null;
  phone: string | null;
  createdAt: string;
  updatedAt: string | null;
}

export interface UpdatePatientProfileRequest {
  curp?: string | null;
  sex?: PatientSex | null;
  occupationId?: number | null;
  educationLevelId?: number | null;
  maritalStatusId?: number | null;
  religionId?: number | null;
  residenceTypeId?: number | null;
  phone?: string | null;
}
