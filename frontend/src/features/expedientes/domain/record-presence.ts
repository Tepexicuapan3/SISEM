import type { RecordPresence } from "@api/types";

/** sw_presente (5.2): "niega diabetes" es un dato; "no se pregunto" no tiene registro. */
export const PRESENCE_OPTIONS: { value: RecordPresence; label: string }[] = [
  { value: "S", label: "Lo tiene" },
  { value: "N", label: "Lo niega" },
];

/** Mismas reglas que el backend (patient_record_usecase): null si esta bien. */
export function personalPresenceError(values: {
  presence: RecordPresence;
  diagnosisDate: string | null;
}): string | null {
  if (values.presence === "N" && values.diagnosisDate) {
    return "Si el paciente lo niega, quita la fecha de diagnóstico.";
  }
  return null;
}

export function familyPresenceError(values: {
  presence: RecordPresence;
  cieCode: string | null;
  description: string | null;
  isDeceased: boolean;
  causeOfDeath: string | null;
}): string | null {
  if (values.presence !== "N") return null;
  if (values.isDeceased || values.causeOfDeath) {
    return "Si lo niega, no marques finado ni causa de muerte.";
  }
  if (!values.cieCode && !values.description) {
    return "Indica qué padecimiento niega (CIE-10 o descripción).";
  }
  return null;
}
