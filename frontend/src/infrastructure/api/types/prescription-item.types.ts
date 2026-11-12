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
  cuadroBasico: "BASICO" | "ESPECIAL" | "INSTITUCIONAL";
  isControlled: boolean;
  /** Especial o controlado: la receta pide autorizacion antes de imprimirse. */
  requiresAuthorization: boolean;
  dose: string | null;
  indications: string;
  /** Via, frecuencia y duracion (RIS art. 30). null en medicamentos guardados antes de exigirlas. */
  route: string | null;
  routeLabel: string | null;
  frequency: string | null;
  duration: string | null;
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
  /** Obligatorias en cada medicamento nuevo (el backend responde 422 sin ellas). */
  route: string;
  frequency: string;
  duration: string;
  // Cruce receta<->alergia: se manda en `true` cuando el medico ya vio la
  // advertencia (AllergyWarning) y decide continuar de todas formas.
  acknowledgeAllergyWarning?: boolean;
}

/** Correccion de un renglon (el medicamento no cambia). */
export type UpdatePrescriptionItemRequest = Omit<
  AddPrescriptionItemRequest,
  "medicationId" | "acknowledgeAllergyWarning"
>;

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
