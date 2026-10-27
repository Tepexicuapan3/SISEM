export type PrescriptionItemStatus = "activo" | "cancelado";

export interface PrescriptionItem {
  id: number;
  visitId: number;
  /** Folio de la receta a la que pertenece ("RX-<anio>-<n>", 5.3). */
  prescriptionFolio: string | null;
  medicationId: number;
  medicationName: string;
  genericName: string | null;
  presentation: string | null;
  dose: string | null;
  indications: string;
  quantity: number;
  status: PrescriptionItemStatus;
  /** Candado de receta (5.3): lo que farmacia ya surtio no se quita. */
  dispensedQuantity: number;
  dispensationStatus: "pendiente" | "parcial" | "dispensado";
  canCancel: boolean;
  createdAt: string;
}

export interface VisitPrescriptionItemsResponse {
  items: PrescriptionItem[];
  total: number;
}

export interface AddPrescriptionItemRequest {
  medicationId: number;
  quantity: number;
  indications: string;
  dose?: string;
  // Cruce receta<->alergia: se manda en `true` cuando el medico ya vio la
  // advertencia (AllergyWarning) y decide continuar de todas formas.
  acknowledgeAllergyWarning?: boolean;
}

export interface AllergyWarning {
  /** null si la alergia viene del sistema anterior y nadie la confirmo todavia. */
  allergyId: number | null;
  substance: string;
  /** L leve, M moderada, G grave (codigos del documento). null en las del sistema anterior. */
  severity: "L" | "M" | "G" | null;
  reaction: string | null;
  /** Alergia del sistema anterior, sin confirmar (no esta en el expediente de SIRES). */
  fromLegacy?: boolean;
  legacyOrigin?: string;
}

export interface AllergyAcknowledgedInfo {
  allergyId: number | null;
  substance: string;
  fromLegacy?: boolean;
}

// El backend NO crea el item si hay una alergia activa que choca con el
// medicamento y todavia no se reconocio la advertencia -- devuelve esto en
// su lugar (200, no 201) para que el frontend muestre la alerta.
export interface AddPrescriptionItemRequiresAcknowledgment {
  requiresAcknowledgment: true;
  allergyWarning: AllergyWarning;
}

export type AddPrescriptionItemResult =
  | (PrescriptionItem & { allergyWarningAcknowledged?: AllergyAcknowledgedInfo })
  | AddPrescriptionItemRequiresAcknowledgment;
