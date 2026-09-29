/**
 * HC_ESTOMATOLOGIA (historia clinica unificada): solo lo propio de la
 * seccion dental. Antecedentes, habitos y alergias viven en los registros
 * permanentes compartidos (ver unified-history.types.ts / allergy.types.ts).
 */
export type OralHygiene = "good" | "regular" | "poor";

export interface StomatologyHistory {
  id: number;
  noExp: string;
  pkNum: number;
  oralHygiene: OralHygiene | null;
  brushingsPerDay: number | null;
  usesFloss: boolean | null;
  softTissues: string | null;
  tmj: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string | null;
}

export type UpdateStomatologyHistoryRequest = Partial<
  Omit<StomatologyHistory, "id" | "noExp" | "pkNum" | "isActive" | "createdAt" | "updatedAt">
>;
