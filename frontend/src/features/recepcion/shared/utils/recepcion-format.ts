import {
  ARRIVAL_TYPE,
  VISIT_STATUS,
  type ArrivalType,
  type VisitStatus,
} from "@api/types";
import {
  RECEPCION_SERVICE,
  type RecepcionService,
} from "@features/recepcion/shared/domain/recepcion.services";

const STATUS_LABELS: Record<VisitStatus, string> = {
  [VISIT_STATUS.EN_ESPERA]: "En espera",
  [VISIT_STATUS.EN_SOMATOMETRIA]: "En somatometria",
  [VISIT_STATUS.LISTA_PARA_DOCTOR]: "Lista para doctor",
  [VISIT_STATUS.EN_CONSULTA]: "En consulta",
  [VISIT_STATUS.CERRADA]: "Cerrada",
  [VISIT_STATUS.CANCELADA]: "Cancelada",
  [VISIT_STATUS.NO_SHOW]: "No show",
};

const ARRIVAL_TYPE_LABELS: Record<ArrivalType, string> = {
  [ARRIVAL_TYPE.APPOINTMENT]: "Con cita",
  [ARRIVAL_TYPE.WALK_IN]: "Sin cita",
};

const RECEPCION_SERVICE_LABELS: Record<RecepcionService, string> = {
  [RECEPCION_SERVICE.MEDICINA_GENERAL]: "Medicina general",
  [RECEPCION_SERVICE.ESPECIALIDAD]: "Especialidad",
  [RECEPCION_SERVICE.URGENCIAS]: "Urgencias",
  [RECEPCION_SERVICE.SIN_CLASIFICAR]: "Sin clasificar",
};

const OPEN_STATUS_SET = new Set<VisitStatus>([
  VISIT_STATUS.EN_ESPERA,
  VISIT_STATUS.EN_SOMATOMETRIA,
  VISIT_STATUS.LISTA_PARA_DOCTOR,
  VISIT_STATUS.EN_CONSULTA,
]);

export const formatVisitStatusLabel = (status: VisitStatus): string => {
  return STATUS_LABELS[status] ?? status.replace(/_/g, " ");
};

export const formatArrivalTypeLabel = (arrivalType: ArrivalType): string => {
  return ARRIVAL_TYPE_LABELS[arrivalType];
};

export const formatRecepcionServiceLabel = (
  service: RecepcionService,
): string => {
  return RECEPCION_SERVICE_LABELS[service];
};

export const isOpenVisitStatus = (status: VisitStatus): boolean => {
  return OPEN_STATUS_SET.has(status);
};

export function formatCitaFechaHora(iso: string): string {
  return new Date(iso).toLocaleString("es-MX", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "America/Mexico_City",
  });
}

// ─── Mapa de parentesco → etiqueta legible ────────────────────────────────────

const PARENTESCO_LABEL: Record<string, string> = {
  TRABAJADOR: "Titular",
  ESPOSA:     "Cónyuge",
  ESPOSO:     "Cónyuge",
  CONYUGE:    "Cónyuge",
  HIJO:       "Hijo(a)",
  HIJA:       "Hijo(a)",
  MADRE:      "Madre",
  PADRE:      "Padre",
  CONCUBINO:  "Concubino(a)",
  CONCUBINA:  "Concubino(a)",
};

export function resolveParentesco(raw: string | null | undefined): string {
  if (!raw) return "Familiar";
  const upper = raw.toUpperCase();
  return PARENTESCO_LABEL[upper] ?? raw;
}

// Fecha y hora de la ficha en hora de la Ciudad de México.
export function formatFichaFechaHora(iso: string): string {
  return new Date(iso).toLocaleString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Mexico_City",
  });
}
