export type AllergyCategory =
  | "medication"
  | "dental_material"
  | "anesthesia"
  | "food"
  | "environmental"
  | "other";

export type AllergySeverity = "mild" | "moderate" | "severe";

export type AllergySource = "general" | "stomatology";

export interface Allergy {
  id: number;
  noExp: string;
  pkNum: number;
  category: AllergyCategory;
  substance: string;
  medicationId: number | null;
  severity: AllergySeverity;
  reaction: string | null;
  source: AllergySource;
  isActive: boolean;
  createdAt: string;
  updatedAt: string | null;
}

export interface PatientAllergiesResponse {
  items: Allergy[];
}

export interface CreateAllergyRequest {
  category: AllergyCategory;
  substance: string;
  medicationId?: number | null;
  severity: AllergySeverity;
  reaction?: string | null;
  source?: AllergySource;
}

export type UpdateAllergyRequest = Partial<
  Omit<CreateAllergyRequest, "source">
>;
