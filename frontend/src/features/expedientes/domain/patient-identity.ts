import type { CurpSource, PatientProfile, PatientSex } from "@api/types";

export const PATIENT_SEX_LABELS: Record<PatientSex, string> = {
  M: "Masculino",
  F: "Femenino",
  X: "No binario",
};

/** La CURP (RENAPO) usa H = Hombre y M = Mujer: se convierte a la de SIRES. */
const CURP_SEX: Record<string, PatientSex> = { H: "M", M: "F", X: "X" };

/** Origen de la CURP (documento "Historia Clinica Unificada", 5.1). */
export const CURP_SOURCE_LABELS: Record<CurpSource, string> = {
  O: "Capital Humano (SERMED)",
  C: "Capturada en SIRES",
};

/**
 * Misma estructura RENAPO que valida el backend (`CURP_REGEX` en
 * consulta_medica/services/curp_rules.py) -- se valida aca solo para dar
 * feedback inmediato; el backend sigue siendo la validacion final.
 */
const CURP_REGEX =
  /^[A-Z][AEIOUX][A-Z]{2}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[HMX](AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)[B-DF-HJ-NP-TV-Z]{3}[A-Z\d]\d$/;

export const normalizeCurp = (value: string) => value.trim().toUpperCase();

export const isValidCurp = (value: string) => CURP_REGEX.test(normalizeCurp(value));

/**
 * Fecha de nacimiento de la CURP como "AAAA-MM-DD". La posicion 17 indica el
 * siglo: digito = nacido antes del 2000, letra = del 2000 en adelante.
 */
export const curpBirthDate = (curp: string): string | null => {
  const value = normalizeCurp(curp);
  if (!isValidCurp(value)) return null;
  const century = /\d/.test(value[16]) ? "19" : "20";
  return `${century}${value.slice(4, 6)}-${value.slice(6, 8)}-${value.slice(8, 10)}`;
};

/** Sexo de SIRES segun la posicion 11 de la CURP (H -> M, M -> F, X -> X). */
export const curpSex = (curp: string): PatientSex | null => {
  const value = normalizeCurp(curp);
  return isValidCurp(value) ? CURP_SEX[value[10]] ?? null : null;
};

const formatDate = (iso: string) => {
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
};

/**
 * Diferencias entre la CURP y los datos del paciente, con el mismo criterio
 * que el backend: lo que no se conoce no se compara.
 */
export const curpMismatches = (
  curp: string,
  { sex, birthDate }: { sex?: PatientSex | null; birthDate?: string | null },
): { sex?: string; birthDate?: string } => {
  const errors: { sex?: string; birthDate?: string } = {};
  const letter = curpSex(curp);
  const date = curpBirthDate(curp);
  if (sex && letter && letter !== sex) {
    errors.sex = `La CURP es de ${PATIENT_SEX_LABELS[letter].toLowerCase()}; el sexo capturado es ${PATIENT_SEX_LABELS[sex].toLowerCase()}.`;
  }
  if (birthDate && date && date !== birthDate) {
    errors.birthDate = `La CURP indica nacimiento el ${formatDate(date)} y el paciente tiene ${formatDate(birthDate)}.`;
  }
  return errors;
};

/** Nombre completo copiado de SERMED, o null si todavia no se sincronizo. */
export const patientFullName = (
  profile: Pick<PatientProfile, "paternalSurname" | "maternalSurname" | "firstName">,
): string | null => {
  const parts = [profile.firstName, profile.paternalSurname, profile.maternalSurname].filter(Boolean);
  return parts.length ? parts.join(" ") : null;
};

export const formatBirthDate = (iso: string | null) => (iso ? formatDate(iso) : null);

/** La CURP vino de Capital Humano: SIRES no la edita. */
export const isCurpFromSermed = (profile: Pick<PatientProfile, "curpSource">) => profile.curpSource === "O";

export interface ProfileSaveError {
  /** Campo del formulario donde se muestra el error, si aplica. */
  field?: "curp" | "sex";
  fieldMessage?: string;
  title: string;
  description: string;
}

/**
 * Traduce el error del backend al guardar la ficha a un mensaje para el
 * usuario. Codigos del backend: CURP_FROM_SERMED (409),
 * CURP_ALREADY_REGISTERED (409, details.noExp) y VALIDATION_ERROR (422).
 */
export const describeProfileSaveError = (error: {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
}): ProfileSaveError => {
  const details = error.details ?? {};
  const firstMessage = (key: string) => {
    const value = details[key];
    if (Array.isArray(value)) return typeof value[0] === "string" ? value[0] : undefined;
    return typeof value === "string" ? value : undefined;
  };

  if (error.code === "CURP_FROM_SERMED") {
    return {
      field: "curp",
      fieldMessage: "Esta CURP viene de Capital Humano y no se edita en SIRES.",
      title: "La CURP no se puede cambiar",
      description: "Si está mal, la tiene que corregir Capital Humano en su sistema.",
    };
  }
  if (error.code === "CURP_ALREADY_REGISTERED") {
    const noExp = typeof details.noExp === "string" ? details.noExp : undefined;
    return {
      field: "curp",
      fieldMessage: noExp ? `Ya pertenece al expediente ${noExp}.` : "Ya pertenece a otro paciente.",
      title: "Esta CURP ya está registrada",
      description: "Puede ser la misma persona con dos expedientes. Avisa para que se revise antes de capturarla.",
    };
  }
  if (firstMessage("sex") || firstMessage("birthDate")) {
    const sexMessage = firstMessage("sex");
    return {
      field: sexMessage ? "sex" : "curp",
      fieldMessage: sexMessage ?? firstMessage("birthDate"),
      title: "La CURP no coincide con los datos del paciente",
      description: "Revisa la CURP y el sexo capturados.",
    };
  }
  if (firstMessage("curp")) {
    return {
      field: "curp",
      fieldMessage: "CURP con formato inválido",
      title: "No se pudo guardar la ficha del paciente",
      description: "Revisa la CURP capturada.",
    };
  }
  return {
    title: "No se pudo guardar la ficha del paciente",
    description: "Intenta nuevamente en unos segundos.",
  };
};
