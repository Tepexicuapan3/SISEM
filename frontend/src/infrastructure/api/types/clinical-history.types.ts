/**
 * Nucleo del paciente (documento "Historia Clinica Unificada", 5.1).
 */

/** H = Hombre, M = Mujer, X = No binario (mismas letras que el CURP). */
export type PatientSex = "H" | "M" | "X";

/** HISTORIA_CLINICA: cabecera unica del paciente (solo lectura). */
export interface ClinicalHistory {
  id: number;
  noExp: string;
  pkNum: number;
  patientId: number;
  openedOn: string | null;
  openingClinicCode: number | null;
  openingDoctorCode: string | null;
  isActive: boolean;
  createdAt: string;
}

/** PACIENTE: identidad y datos sociodemograficos (editable, versionado). */
export interface PatientProfile {
  id: number;
  noExp: string;
  pkNum: number;
  curp: string | null;
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
