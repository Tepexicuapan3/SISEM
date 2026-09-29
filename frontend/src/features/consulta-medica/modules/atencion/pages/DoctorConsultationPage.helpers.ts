import { ApiError } from "@api/utils/errors";
import {
  VISIT_SERVICE,
  VISIT_STATUS,
  type CieSearchItem,
  type VisitStatus,
} from "@api/types";
import type {
  SaveDiagnosisFormInput,
  SavePrescriptionsFormInput,
  SaveDiagnosisFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";

export const DOCTOR_QUEUE_PERMISSION_REQUIREMENT = {
  allOf: ["clinico:consultas:read"],
} as const;

export const DOCTOR_WRITE_PERMISSION_REQUIREMENT = {
  allOf: ["clinico:consultas:read"],
} as const;

export const START_CONSULTATION_DOMAIN_ERROR_MESSAGE: Record<
  | "ROLE_NOT_ALLOWED"
  | "VISIT_STATE_INVALID"
  | "VISIT_NOT_FOUND"
  | "PERMISSION_DENIED",
  string
> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para iniciar consulta.",
  VISIT_STATE_INVALID:
    "La visita ya no esta en un estado valido para iniciar consulta.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue actualizada por otro usuario.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
};

export const SAVE_DIAGNOSIS_DOMAIN_ERROR_MESSAGE: Record<
  | "ROLE_NOT_ALLOWED"
  | "VISIT_STATE_INVALID"
  | "VISIT_NOT_FOUND"
  | "VALIDATION_ERROR"
  | "PERMISSION_DENIED",
  string
> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para guardar diagnostico.",
  VISIT_STATE_INVALID:
    "La visita ya no esta en consulta. Actualiza la bandeja del doctor.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  VALIDATION_ERROR: "Revisa los campos del diagnostico antes de guardar.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
};

export const SAVE_PRESCRIPTIONS_DOMAIN_ERROR_MESSAGE: Record<
  | "ROLE_NOT_ALLOWED"
  | "VISIT_STATE_INVALID"
  | "VISIT_NOT_FOUND"
  | "VALIDATION_ERROR"
  | "PERMISSION_DENIED",
  string
> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para guardar receta.",
  VISIT_STATE_INVALID:
    "La visita ya no esta en consulta. Actualiza la bandeja del doctor.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  VALIDATION_ERROR: "Agrega al menos una indicacion valida de receta.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
};

export const CLOSE_CONSULTATION_DOMAIN_ERROR_MESSAGE: Record<
  | "ROLE_NOT_ALLOWED"
  | "VISIT_STATE_INVALID"
  | "VISIT_NOT_FOUND"
  | "VALIDATION_ERROR"
  | "PERMISSION_DENIED"
  | "CONFLICT_DUPLICATE_ACTION",
  string
> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para cerrar consulta.",
  VISIT_STATE_INVALID:
    "La visita ya no esta en un estado valido para cerrar consulta.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  VALIDATION_ERROR:
    "Completa diagnostico y nota final para cerrar la consulta.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
  CONFLICT_DUPLICATE_ACTION:
    "La consulta ya fue cerrada con informacion diferente. Actualiza la bandeja.",
};

export const FALLBACK_START_CONSULTATION_ERROR_MESSAGE =
  "No se pudo iniciar la consulta. Intenta nuevamente.";
export const FALLBACK_SAVE_DIAGNOSIS_ERROR_MESSAGE =
  "No se pudo guardar el diagnostico. Intenta nuevamente.";
export const FALLBACK_SAVE_PRESCRIPTIONS_ERROR_MESSAGE =
  "No se pudo guardar la receta. Intenta nuevamente.";
export const FALLBACK_CLOSE_CONSULTATION_ERROR_MESSAGE =
  "No se pudo cerrar la consulta. Intenta nuevamente.";

export const SERVICE_TYPE_LABEL: Record<string, string> = {
  [VISIT_SERVICE.MEDICINA_GENERAL]: "Medicina general",
  [VISIT_SERVICE.ESPECIALIDAD]: "Especialidad",
  [VISIT_SERVICE.URGENCIAS]: "Urgencias",
};

export const ARRIVAL_LABEL: Record<string, string> = {
  appointment: "Con cita",
  walk_in: "Sin cita",
};

export const OPEN_VISIT_STATUSES = new Set<VisitStatus>([
  VISIT_STATUS.LISTA_PARA_DOCTOR,
  VISIT_STATUS.EN_CONSULTA,
]);

export const MISSING_VITAL_VALUE = "No registrado";

export const DEFAULT_DIAGNOSIS_FORM_VALUES: SaveDiagnosisFormInput = {
  primaryDiagnosis: "",
  finalNote: "",
  cieCode: "",
  currentIllness: "",
  systemsReview: "",
  diagnosticPlan: "",
  therapeuticPlan: "",
};

export const DEFAULT_PRESCRIPTIONS_FORM_VALUES: SavePrescriptionsFormInput = {
  itemsText: "",
};

export interface VisitStatusOverrideState {
  visitId: number;
  status: VisitStatus;
}

export const formatStatusLabel = (status: string): string => {
  return status.replace(/_/g, " ");
};

export const formatServiceTypeLabel = (serviceType: string): string => {
  return SERVICE_TYPE_LABEL[serviceType] ?? serviceType;
};

/** Fecha/hora legible del momento de captura de los signos vitales
 * (`VisitVitalsPayload.capturedAt`), para que el medico vea cuando se
 * tomaron -- no solo el dato crudo. */
export const formatCapturedAtTime = (
  capturedAt: string | null | undefined,
): string => {
  if (!capturedAt) return MISSING_VITAL_VALUE;

  const date = new Date(capturedAt);
  if (Number.isNaN(date.getTime())) return MISSING_VITAL_VALUE;

  return date.toLocaleString("es-MX", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
};

export const formatArrivalTypeLabel = (arrivalType: string): string => {
  return ARRIVAL_LABEL[arrivalType] ?? arrivalType;
};

export const formatOptionalMetric = (
  value: number | null | undefined,
  options: {
    digits?: number;
  } = {},
): string => {
  if (value === null || value === undefined) {
    return MISSING_VITAL_VALUE;
  }

  const digits = options.digits ?? 0;
  return digits > 0 ? value.toFixed(digits) : value.toString();
};

export const formatBloodPressure = (
  systolic: number | null | undefined,
  diastolic: number | null | undefined,
): string => {
  const hasSystolic = systolic !== null && systolic !== undefined;
  const hasDiastolic = diastolic !== null && diastolic !== undefined;

  if (!hasSystolic && !hasDiastolic) {
    return MISSING_VITAL_VALUE;
  }

  if (systolic === null || systolic === undefined) {
    return `-- / ${diastolic}`;
  }

  if (diastolic === null || diastolic === undefined) {
    return `${systolic} / --`;
  }

  return `${systolic} / ${diastolic}`;
};

export const formatMetricWithUnit = (
  value: number | null | undefined,
  unit: string,
  options: {
    digits?: number;
  } = {},
): string => {
  const formatted = formatOptionalMetric(value, options);
  if (formatted === MISSING_VITAL_VALUE) {
    return formatted;
  }

  return `${formatted} ${unit}`;
};

export const formatSomatometriaNotes = (value: string | null | undefined): string => {
  const normalized = value?.trim();
  if (!normalized) {
    return "Sin observaciones de somatometria registradas.";
  }

  return normalized;
};

// ── Helpers hora/fecha de cita ────────────────────────────────────────────────

export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.includes("T") ? iso : `${iso}T00:00:00`);
  return d.toLocaleDateString("es-MX", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function getMinutesUntilAppointment(horaConsulta: string | null, now: Date): number | null {
  if (!horaConsulta) return null;
  const [h, m] = horaConsulta.split(":").map(Number);
  const appt = h * 60 + m;
  const curr = now.getHours() * 60 + now.getMinutes();
  return appt - curr;
}

export const hasVitalValue = (value: number | null | undefined): boolean => {
  return value !== null && value !== undefined;
};

export const resolveDomainErrorMessage = <TDomainCode extends string>(
  error: unknown,
  domainErrors: Record<TDomainCode, string>,
  fallback: string,
): string => {
  if (!(error instanceof ApiError)) {
    return fallback;
  }

  const domainCode = error.code as TDomainCode;
  if (Object.prototype.hasOwnProperty.call(domainErrors, domainCode)) {
    return domainErrors[domainCode];
  }

  return error.message || fallback;
};

export const toPrescriptionItems = (itemsText: string): string[] => {
  return itemsText
    .split("\n")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
};

export const buildDiagnosisFingerprint = ({
  primaryDiagnosis,
  finalNote,
  cieCode,
  currentIllness,
  systemsReview,
  diagnosticPlan,
  therapeuticPlan,
}: SaveDiagnosisFormValues): string => {
  return [
    primaryDiagnosis.trim(),
    finalNote.trim(),
    cieCode.trim().toUpperCase(),
    currentIllness.trim(),
    systemsReview.trim(),
    diagnosticPlan.trim(),
    therapeuticPlan.trim(),
  ].join("::");
};

// Payload comun de guardar diagnostico y cerrar consulta. Los campos de
// his_notas ampliada se envian siempre (vacio -> null en backend) para que
// borrar un texto ya guardado tambien quede registrado.
export const buildDiagnosisPayload = (values: SaveDiagnosisFormValues) => {
  const normalizedCieCode = normalizeCieCode(values.cieCode);
  return {
    primaryDiagnosis: values.primaryDiagnosis,
    finalNote: values.finalNote,
    ...(normalizedCieCode ? { cieCode: normalizedCieCode } : {}),
    currentIllness: values.currentIllness,
    systemsReview: values.systemsReview,
    diagnosticPlan: values.diagnosticPlan,
    therapeuticPlan: values.therapeuticPlan,
  };
};

export const normalizeCieCode = (value: string): string | undefined => {
  const normalized = value.trim().toUpperCase();
  return normalized.length > 0 ? normalized : undefined;
};

export const formatCieLabel = (cie: CieSearchItem): string => {
  return `${cie.code} - ${cie.description}`;
};
