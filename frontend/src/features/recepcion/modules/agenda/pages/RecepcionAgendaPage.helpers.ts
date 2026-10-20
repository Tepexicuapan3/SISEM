import { addDays } from "@features/recepcion/modules/citas/utils/dates";
import {
  ARRIVAL_TYPE,
  RECEPCION_STATUS_ACTION,
  VISIT_STATUS,
  type EstatusCita,
  type VisitQueueItem,
  type VisitStatus,
} from "@api/types";
import { ApiError } from "@api/utils/errors";
import {
  RECEPCION_SERVICE,
  resolveRecepcionService,
  type RecepcionService,
} from "@features/recepcion/shared/domain/recepcion.services";
import { isOpenVisitStatus } from "@features/recepcion/shared/utils/recepcion-format";

// ─── Constantes historial NOM-024 ────────────────────────────────────────────

export const ESTATUS_LABEL: Record<EstatusCita, string> = {
  agendada:   "Agendada",
  confirmada: "Confirmada",
  atendida:   "Atendida",
  cancelada:  "Cancelada",
  no_asistio: "No asistió",
};

export const ESTATUS_VARIANT: Record<EstatusCita,
  "outline" | "stable" | "alert" | "secondary" | "critical"
> = {
  agendada:   "outline",
  confirmada: "stable",
  atendida:   "secondary",
  cancelada:  "critical",
  no_asistio: "alert",
};

export function getBandejaPeriodRange(period: string, customDesde: string, customHasta: string) {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const todayStr = fmt(today);
  switch (period) {
    case "week": {
      const d = new Date(today);
      const day = d.getDay();
      d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
      return { fechaDesde: fmt(d), fechaHasta: todayStr };
    }
    case "month":  return { fechaDesde: fmt(new Date(today.getFullYear(), today.getMonth(), 1)), fechaHasta: todayStr };
    case "year":   return { fechaDesde: `${today.getFullYear()}-01-01`, fechaHasta: todayStr };
    case "custom": return { fechaDesde: customDesde, fechaHasta: customHasta };
    default:       return { fechaDesde: todayStr, fechaHasta: todayStr };
  }
}

export const BANDEJA_PERIOD_LABEL: Record<string, string> = {
  today:  "Hoy (tiempo real)",
  week:   "Esta semana",
  month:  "Este mes",
  year:   "Este año",
  custom: "Personalizado",
};

export function getMonday(date: Date): string {
  const d = new Date(date);
  const day = d.getDay();
  d.setDate(d.getDate() - day + (day === 0 ? -6 : 1));
  return d.toISOString().slice(0, 10);
}

export function formatWeekRange(weekStart: string): string {
  const from = new Date(weekStart + "T00:00:00");
  const to   = new Date(addDays(weekStart, 6) + "T00:00:00");
  const fmt  = (d: Date) => d.toLocaleDateString("es-MX", { day: "2-digit", month: "short" });
  return `${fmt(from)} — ${fmt(to)}`;
}

export const RECEPCION_ACTION = {
  EN_SOMATOMETRIA: RECEPCION_STATUS_ACTION.EN_SOMATOMETRIA,
  CANCELADA: RECEPCION_STATUS_ACTION.CANCELADA,
  NO_SHOW: RECEPCION_STATUS_ACTION.NO_SHOW,
} as const;

export type RecepcionAction = (typeof RECEPCION_ACTION)[keyof typeof RECEPCION_ACTION];

export interface PendingStatusAction {
  visitId: number;
  folio: string;
  targetStatus: RecepcionAction;
}

export const RECEPCION_ACTION_COPY: Record<
  RecepcionAction,
  {
    label: string;
    confirmLabel: string;
    successMessage: string;
    getDescription: (folio: string) => string;
  }
> = {
  [RECEPCION_ACTION.EN_SOMATOMETRIA]: {
    label: "Llego",
    confirmLabel: "Enviar a somatometria",
    successMessage: "Paciente enviado a somatometria.",
    getDescription: (folio) =>
      `Vas a marcar la visita ${folio} como llegada y enviarla a somatometria.`,
  },
  [RECEPCION_ACTION.CANCELADA]: {
    label: "Cancelada",
    confirmLabel: "Marcar cancelada",
    successMessage: "Visita marcada como cancelada.",
    getDescription: (folio) =>
      `Vas a marcar la visita ${folio} como cancelada. Esta accion no se puede deshacer.`,
  },
  [RECEPCION_ACTION.NO_SHOW]: {
    label: "No llego",
    confirmLabel: "Marcar no llego",
    successMessage: "Visita marcada como no show.",
    getDescription: (folio) =>
      `Vas a marcar la visita ${folio} como no llegada. Esta accion no se puede deshacer.`,
  },
};

export const VISIT_STATUS_DOMAIN_ERROR_MESSAGE: Record<
  | "ROLE_NOT_ALLOWED"
  | "VISIT_STATE_INVALID"
  | "VISIT_NOT_FOUND"
  | "VALIDATION_ERROR"
  | "PERMISSION_DENIED"
  | "VISIT_MOTIVO_REQUERIDO",
  string
> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para actualizar estados en recepcion.",
  VISIT_STATE_INVALID:
    "La visita ya no esta en un estado valido para esta accion. Actualiza la cola.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  VALIDATION_ERROR: "No se pudo procesar la accion solicitada.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
  VISIT_MOTIVO_REQUERIDO: "Se requiere un motivo para cancelar la visita.",
};

export const FALLBACK_VISIT_STATUS_ERROR_MESSAGE =
  "No se pudo actualizar el estado de la visita. Intenta nuevamente.";

export const RETRYABLE_STATUS_ACTION_ERRORS = [
  "VISIT_STATE_INVALID",
  "VISIT_NOT_FOUND",
] as const;

export const STATUS_FILTER = {
  ALL: "all",
  OPEN: "open",
  EN_ESPERA: VISIT_STATUS.EN_ESPERA,
  EN_SOMATOMETRIA: VISIT_STATUS.EN_SOMATOMETRIA,
  LISTA_PARA_DOCTOR: VISIT_STATUS.LISTA_PARA_DOCTOR,
  EN_CONSULTA: VISIT_STATUS.EN_CONSULTA,
  CERRADA: VISIT_STATUS.CERRADA,
  CANCELADA: VISIT_STATUS.CANCELADA,
  NO_SHOW: VISIT_STATUS.NO_SHOW,
} as const;

export type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

export const ARRIVAL_TYPE_FILTER = {
  ALL: "all",
  APPOINTMENT: ARRIVAL_TYPE.APPOINTMENT,
  WALK_IN: ARRIVAL_TYPE.WALK_IN,
} as const;

export type ArrivalTypeFilter =
  (typeof ARRIVAL_TYPE_FILTER)[keyof typeof ARRIVAL_TYPE_FILTER];

export const SERVICE_FILTER = {
  ALL: "all",
  MEDICINA_GENERAL: RECEPCION_SERVICE.MEDICINA_GENERAL,
  ESPECIALIDAD: RECEPCION_SERVICE.ESPECIALIDAD,
  URGENCIAS: RECEPCION_SERVICE.URGENCIAS,
} as const;

export type ServiceFilter = (typeof SERVICE_FILTER)[keyof typeof SERVICE_FILTER];

const getOpenPriority = (visitStatus: VisitStatus): number =>
  isOpenVisitStatus(visitStatus) ? 0 : 1;

const getUrgenciasPriority = (visit: VisitQueueItem): number =>
  resolveRecepcionService(visit) === RECEPCION_SERVICE.URGENCIAS ? 0 : 1;

const getArrivalTypePriority = (visit: VisitQueueItem): number =>
  visit.arrivalType === ARRIVAL_TYPE.APPOINTMENT ? 0 : 1;

export const matchesStatus = (
  visit: VisitQueueItem,
  statusFilter: StatusFilter,
): boolean => {
  if (statusFilter === STATUS_FILTER.ALL) {
    return true;
  }

  if (statusFilter === STATUS_FILTER.OPEN) {
    return isOpenVisitStatus(visit.status);
  }

  return visit.status === statusFilter;
};

export const matchesArrivalType = (
  visit: VisitQueueItem,
  arrivalTypeFilter: ArrivalTypeFilter,
): boolean => {
  if (arrivalTypeFilter === ARRIVAL_TYPE_FILTER.ALL) {
    return true;
  }

  return visit.arrivalType === arrivalTypeFilter;
};

export const matchesService = (
  visitService: RecepcionService,
  serviceFilter: ServiceFilter,
): boolean => {
  if (serviceFilter === SERVICE_FILTER.ALL) {
    return true;
  }

  return visitService === serviceFilter;
};

export const matchesSearch = (visit: VisitQueueItem, searchTerm: string): boolean => {
  const normalizedSearch = searchTerm.trim().toLowerCase();
  if (!normalizedSearch) {
    return true;
  }

  const noExp         = visit.noExp.toLowerCase();
  const folio         = visit.folio.toLowerCase();
  const appointmentId = (visit.appointmentId ?? "").toLowerCase();

  return (
    folio.includes(normalizedSearch) ||
    noExp.includes(normalizedSearch) ||
    appointmentId.includes(normalizedSearch)
  );
};

export const sortAgendaVisits = (
  firstVisit: VisitQueueItem,
  secondVisit: VisitQueueItem,
) => {
  const openPriorityDifference =
    getOpenPriority(firstVisit.status) - getOpenPriority(secondVisit.status);

  if (openPriorityDifference !== 0) {
    return openPriorityDifference;
  }

  if (
    isOpenVisitStatus(firstVisit.status) &&
    isOpenVisitStatus(secondVisit.status)
  ) {
    const urgenciasPriorityDifference =
      getUrgenciasPriority(firstVisit) - getUrgenciasPriority(secondVisit);

    if (urgenciasPriorityDifference !== 0) {
      return urgenciasPriorityDifference;
    }

    const arrivalTypePriorityDifference =
      getArrivalTypePriority(firstVisit) - getArrivalTypePriority(secondVisit);

    if (arrivalTypePriorityDifference !== 0) {
      return arrivalTypePriorityDifference;
    }
  }

  return firstVisit.folio.localeCompare(secondVisit.folio, "es");
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

export const shouldRefreshQueueAfterError = (error: unknown): boolean => {
  if (!(error instanceof ApiError)) {
    return false;
  }

  return RETRYABLE_STATUS_ACTION_ERRORS.includes(
    error.code as (typeof RETRYABLE_STATUS_ACTION_ERRORS)[number],
  );
};

// ─── Espacios de identidad: médico vs usuario ────────────────────────────────
// `MedicoListItem.id` / `MedicoDisponible.medicoId` = CatMedico.id (No. Médico).
// `Visit.doctorId` vive en el espacio USUARIO (SyUsuario). Nunca se mezclan:
// todo lo que cree o compare visitas usa `usuarioId`.

/** Opciones del filtro "médico" de la bandeja: id = usuarioId (compara con visit.doctorId). */
export function buildDoctorFilterOptions(
  medicos: { usuarioId: number; nombreCompleto: string }[],
): { id: number; nombre: string }[] {
  return medicos.map((m) => ({ id: m.usuarioId, nombre: m.nombreCompleto }));
}
