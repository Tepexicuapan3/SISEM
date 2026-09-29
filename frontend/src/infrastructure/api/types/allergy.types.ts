/** Documento: L leve, M moderada, G grave. */
export type AllergySeverity = "L" | "M" | "G";

export type AllergySource = "general" | "stomatology";

/** Documento: A activa, R resuelta (visible, ya no alerta), E capturada por error. */
export type AllergyStatus = "A" | "R" | "E";

export interface ChangeAllergyStatusRequest {
  status: AllergyStatus;
  reason: string;
}

export interface Allergy {
  id: number;
  noExp: string;
  pkNum: number;
  /** CAT_TIPO_ALERGIA: 1 medicamento, 2 anestesia, 3 material dental, 4 ambiental, 5 alimento, 9 otro. */
  allergyTypeId: number;
  allergyTypeName: string;
  substance: string;
  medicationId: number | null;
  severity: AllergySeverity;
  reaction: string | null;
  source: AllergySource;
  status: AllergyStatus;
  statusReason: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string | null;
}

export interface PatientAllergiesResponse {
  items: Allergy[];
}

export interface CreateAllergyRequest {
  allergyTypeId: number;
  substance: string;
  medicationId?: number | null;
  severity: AllergySeverity;
  reaction?: string | null;
  source?: AllergySource;
}

export type UpdateAllergyRequest = Partial<
  Omit<CreateAllergyRequest, "source">
>;
