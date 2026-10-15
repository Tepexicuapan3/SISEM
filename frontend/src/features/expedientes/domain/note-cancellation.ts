import type {
  NoteCancellationBlocker,
  NoteCancellationCascadeCounts,
  NoteCancellationPreview,
} from "@api/types";

/** Mensajes legibles por codigo de bloqueo (409). */
const BLOCKER_MESSAGES: Record<string, string> = {
  PRESCRIPTION_ITEM_DISPENSED:
    "Hay medicamentos de la receta que ya fueron surtidos (total o parcialmente).",
  LEAVE_SENT_TO_RH: "Hay una incapacidad que ya fue enviada o verificada por RH.",
  STUDY_RESULT_ACTIVE:
    "Hay resultados de estudio activos ligados a la consulta o a sus pases.",
};

export const describeBlocker = (blocker: NoteCancellationBlocker): string =>
  BLOCKER_MESSAGES[blocker.code] ?? blocker.message;

/** Mensajes legibles por codigo de error de la cancelacion. */
const ERROR_MESSAGES: Record<string, string> = {
  ROLE_NOT_ALLOWED: "No tienes permiso para cancelar notas.",
  AUTHORIZER_NOT_DESIGNATED:
    "No tienes una designacion vigente de autorizador que cubra el centro de esta nota.",
  SELF_AUTHORIZATION_NOT_ALLOWED:
    "No puedes cancelar una nota de la que eres el medico tratante.",
  REAUTH_FAILED: "La contrasena es incorrecta.",
  REAUTH_LOCKED:
    "Demasiados intentos fallidos. La verificacion de contrasena esta bloqueada temporalmente; intenta mas tarde.",
  NOTE_ALREADY_CANCELLED: "La nota ya fue cancelada.",
  VISIT_STATE_INVALID: "Solo se puede cancelar una nota con la consulta cerrada.",
  NOTE_CENTER_UNRESOLVED: "No se pudo determinar el centro de atencion de la nota.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de continuar.",
  VISIT_NOT_FOUND: "La visita ya no existe.",
  CONSULTATION_NOT_FOUND: "La visita no tiene una consulta registrada.",
  SERVICE_UNAVAILABLE: "No se pudo verificar tu contrasena en este momento. Intenta nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export interface NoteCancellationErrorInfo {
  code: string | null;
  message: string;
  blockers: NoteCancellationBlocker[];
  /** La contrasena se invalida (se limpia el campo). */
  clearPassword: boolean;
  /** El envio queda deshabilitado (REAUTH_LOCKED). */
  lockSubmit: boolean;
  /** El estado de la nota cambio: conviene refrescar preview/historial. */
  stale: boolean;
}

const BLOCKER_CODES = new Set(Object.keys(BLOCKER_MESSAGES));

const readBlockers = (details: unknown): NoteCancellationBlocker[] => {
  if (typeof details !== "object" || details === null) return [];
  const raw = (details as { blockers?: unknown }).blockers;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (item): item is NoteCancellationBlocker =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as { code?: unknown }).code === "string",
  );
};

export const mapNoteCancellationError = (error: unknown): NoteCancellationErrorInfo => {
  const err = (typeof error === "object" && error !== null ? error : {}) as {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
  const code = typeof err.code === "string" ? err.code : null;
  const blockers = readBlockers(err.details);
  const isBlockerError = code !== null && BLOCKER_CODES.has(code);

  let message =
    (code !== null ? ERROR_MESSAGES[code] : undefined) ??
    (isBlockerError ? BLOCKER_MESSAGES[code as string] : undefined) ??
    (typeof err.message === "string" && err.message ? err.message : "No se pudo cancelar la nota.");
  if (isBlockerError && blockers.length > 0) {
    message = "La nota no se puede cancelar:";
  }

  return {
    code,
    message,
    blockers: isBlockerError && blockers.length === 0 && code
      ? [{ code, message: BLOCKER_MESSAGES[code], ids: [] }]
      : blockers,
    clearPassword: code === "REAUTH_FAILED" || code === "REAUTH_LOCKED",
    lockSubmit: code === "REAUTH_LOCKED",
    stale:
      isBlockerError ||
      code === "NOTE_ALREADY_CANCELLED" ||
      code === "VISIT_STATE_INVALID",
  };
};

const CASCADE_LABELS: Array<[keyof NoteCancellationCascadeCounts, string, string]> = [
  ["diagnoses", "diagnostico", "diagnosticos"],
  ["prescriptionItems", "medicamento de receta", "medicamentos de receta"],
  ["prescriptionAuthorizations", "autorizacion de receta pendiente", "autorizaciones de receta pendientes"],
  ["referrals", "pase", "pases"],
  ["referralStudies", "estudio de pase", "estudios de pase"],
  ["medicalLeaves", "incapacidad", "incapacidades"],
];

/** Lineas "N elemento(s)" de la cascada, omitiendo los que valen 0. */
export const describeCascade = (cascade: NoteCancellationCascadeCounts): string[] =>
  CASCADE_LABELS.flatMap(([key, singular, plural]) => {
    const count = cascade[key] ?? 0;
    return count > 0 ? [`${count} ${count === 1 ? singular : plural}`] : [];
  });

/**
 * Por que el preview dice que no se puede enviar (sin contar bloqueos de
 * datos, que se listan aparte). Devuelve null si el actor puede continuar.
 */
export const describePreviewRestriction = (
  preview: NoteCancellationPreview,
): string | null => {
  if (preview.alreadyCancelled) return ERROR_MESSAGES.NOTE_ALREADY_CANCELLED;
  if (preview.visitStatus !== "cerrada") return ERROR_MESSAGES.VISIT_STATE_INVALID;
  if (preview.autoCancelacion) return ERROR_MESSAGES.SELF_AUTHORIZATION_NOT_ALLOWED;
  if (!preview.puedeAutorizar) {
    return preview.puedeAutorizarMotivo === "NOTE_CENTER_UNRESOLVED"
      ? ERROR_MESSAGES.NOTE_CENTER_UNRESOLVED
      : ERROR_MESSAGES.AUTHORIZER_NOT_DESIGNATED;
  }
  return null;
};

export const NOTE_CANCELLATION_INVALIDATION_PREFIXES = [
  ["expedientes", "consultations-history"],
  ["expedientes", "medical-leaves"],
  ["expedientes", "study-results"],
] as const;
