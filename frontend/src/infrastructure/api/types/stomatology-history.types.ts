export interface StomatologyHistory {
  id: number;
  noExp: string;
  pkNum: number;
  familyDiabetes: boolean;
  familyCancer: boolean;
  familyHighBloodPressure: boolean;
  familyLowBloodPressure: boolean;
  causeOfDeath: string | null;
  personalDiabetes: boolean;
  personalAsthma: boolean;
  personalHighBloodPressure: boolean;
  personalLowBloodPressure: boolean;
  personalHepatitis: boolean;
  personalHiv: boolean;
  personalSmoking: boolean;
  personalAlcoholism: boolean;
  personalSubstanceAbuse: boolean;
  habits: string | null;
  diet: string | null;
  surgicalHistory: string | null;
  traumaticHistory: string | null;
  // Los 6 `allergy*` (change `alergias-unificadas`) quedan CONGELADOS en el
  // backend -- reemplazados por `Allergy` (ver allergy.types.ts), ya no se
  // exponen aqui.
  currentIllnessHistory: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string | null;
}

export type UpdateStomatologyHistoryRequest = Partial<
  Omit<StomatologyHistory, "id" | "noExp" | "pkNum" | "isActive" | "createdAt" | "updatedAt">
>;
