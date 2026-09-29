import type { PatientSex } from "@api/types";

export const PATIENT_SEX_LABELS: Record<PatientSex, string> = {
  H: "Hombre",
  M: "Mujer",
  X: "No binario",
};

/**
 * Misma estructura RENAPO que valida el backend (`CURP_REGEX` en
 * consulta_medica/serializers.py) -- se valida aca solo para dar feedback
 * inmediato; el backend sigue siendo la validacion final.
 */
const CURP_REGEX =
  /^[A-Z][AEIOUX][A-Z]{2}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[HMX](AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)[B-DF-HJ-NP-TV-Z]{3}[A-Z\d]\d$/;

export const normalizeCurp = (value: string) => value.trim().toUpperCase();

export const isValidCurp = (value: string) => CURP_REGEX.test(normalizeCurp(value));
