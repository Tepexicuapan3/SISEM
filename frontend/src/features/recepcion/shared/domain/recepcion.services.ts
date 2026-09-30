import {
  ARRIVAL_TYPE,
  type ArrivalType,
  type VisitQueueItem,
} from "@api/types";

export const RECEPCION_SERVICE = {
  MEDICINA_GENERAL: "medicina_general",
  ESPECIALIDAD: "especialidad",
  URGENCIAS: "urgencias",
  SIN_CLASIFICAR: "sin_clasificar",
} as const;

export type RecepcionService =
  (typeof RECEPCION_SERVICE)[keyof typeof RECEPCION_SERVICE];

export type RecepcionKnownService = Exclude<
  RecepcionService,
  typeof RECEPCION_SERVICE.SIN_CLASIFICAR
>;

export const RECEPCION_SERVICE_MODE = {
  PROGRAMADO: "programado",
  INMEDIATO: "inmediato",
} as const;

export type RecepcionServiceMode =
  (typeof RECEPCION_SERVICE_MODE)[keyof typeof RECEPCION_SERVICE_MODE];

export interface RecepcionServiceProfile {
  key: RecepcionKnownService;
  label: string;
  shortLabel: string;
  mode: RecepcionServiceMode;
  defaultArrivalType: ArrivalType;
  forceArrivalType?: ArrivalType;
  description: string;
  queueHint: string;
}

export const RECEPCION_SERVICE_PROFILES: Record<
  RecepcionKnownService,
  RecepcionServiceProfile
> = {
  [RECEPCION_SERVICE.MEDICINA_GENERAL]: {
    key: RECEPCION_SERVICE.MEDICINA_GENERAL,
    label: "Medicina general",
    shortLabel: "General",
    mode: RECEPCION_SERVICE_MODE.PROGRAMADO,
    defaultArrivalType: ARRIVAL_TYPE.APPOINTMENT,
    description: "Atencion de consulta medica general y primera valoracion.",
    queueHint: "Derivar a cola de espera general.",
  },
  [RECEPCION_SERVICE.ESPECIALIDAD]: {
    key: RECEPCION_SERVICE.ESPECIALIDAD,
    label: "Especialidad",
    shortLabel: "Especialidad",
    mode: RECEPCION_SERVICE_MODE.PROGRAMADO,
    defaultArrivalType: ARRIVAL_TYPE.APPOINTMENT,
    description:
      "Atencion especializada con agenda o ingreso directo validado.",
    queueHint: "Validar cita o referencia antes de confirmar llegada.",
  },
  [RECEPCION_SERVICE.URGENCIAS]: {
    key: RECEPCION_SERVICE.URGENCIAS,
    label: "Urgencias",
    shortLabel: "Urgencias",
    mode: RECEPCION_SERVICE_MODE.INMEDIATO,
    defaultArrivalType: ARRIVAL_TYPE.WALK_IN,
    forceArrivalType: ARRIVAL_TYPE.WALK_IN,
    description: "Ingreso inmediato para triage de urgencias.",
    queueHint: "Escalar a triage urgente de forma prioritaria.",
  },
};

export const RECEPCION_SERVICE_LIST: RecepcionKnownService[] = [
  RECEPCION_SERVICE.MEDICINA_GENERAL,
  RECEPCION_SERVICE.ESPECIALIDAD,
  RECEPCION_SERVICE.URGENCIAS,
];

const SERVICE_TAG_PATTERN = /^\[svc:([a-z_]+)\]\s*/i;

export const isRecepcionService = (
  value: string,
): value is RecepcionService => {
  return Object.values(RECEPCION_SERVICE).includes(value as RecepcionService);
};

export const isRecepcionKnownService = (
  value: string,
): value is RecepcionKnownService => {
  return RECEPCION_SERVICE_LIST.includes(value as RecepcionKnownService);
};

export const isServiceForcedToWalkIn = (
  service: RecepcionKnownService,
): boolean => {
  return (
    RECEPCION_SERVICE_PROFILES[service].forceArrivalType ===
    ARRIVAL_TYPE.WALK_IN
  );
};

export const extractRecepcionServiceFromNotes = (
  notes?: string | null,
): RecepcionService | null => {
  if (!notes) {
    return null;
  }

  const match = notes.match(SERVICE_TAG_PATTERN);
  if (!match?.[1]) {
    return null;
  }

  const normalizedService = match[1].toLowerCase();
  return isRecepcionService(normalizedService) ? normalizedService : null;
};

export const stripRecepcionServiceTag = (notes?: string | null): string => {
  if (!notes) {
    return "";
  }

  return notes.replace(SERVICE_TAG_PATTERN, "").trim();
};

export const resolveRecepcionService = (
  visit: Pick<VisitQueueItem, "serviceType" | "notes">,
): RecepcionService => {
  if (isRecepcionKnownService(visit.serviceType)) {
    return visit.serviceType;
  }

  const extractedService = extractRecepcionServiceFromNotes(visit.notes);

  if (!extractedService) {
    return RECEPCION_SERVICE.MEDICINA_GENERAL;
  }

  return extractedService;
};
