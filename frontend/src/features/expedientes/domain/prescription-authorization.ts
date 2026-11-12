import type { PatientConsultationHistoryItem } from "@api/types";

export type PrescriptionAuthorizationState = PatientConsultationHistoryItem["prescriptionAuthorization"];

/**
 * La receta se imprime si no pidio autorizacion o si ya la autorizaron; pendiente
 * o rechazada no (el backend responderia 409).
 */
export const canPrintPrescription = (authorization: PrescriptionAuthorizationState): boolean =>
  authorization === null || authorization.status === "autorizada";
