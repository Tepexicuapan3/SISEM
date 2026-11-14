import { http, HttpResponse } from "msw";
import type { ChronicControlPanel, ChronicVisitNotice } from "@api/types/padrones.types";
import { getApiUrl } from "../urls";

// Aviso y control de cronicos de la consulta: por defecto el paciente no esta
// en el padron (no se pintan). Las pruebas de esos componentes mockean el hook.
const EMPTY_NOTICE: ChronicVisitNotice = { enrollments: [], suggestion: null, canEnroll: false };
const EMPTY_CONTROL: ChronicControlPanel = { programs: [], vitalsCapturedAt: null, canRegister: false };

export const padronesHandlers = [
  http.get(getApiUrl("padrones/cronicos/visita/:visitId/aviso"), () => HttpResponse.json(EMPTY_NOTICE)),
  http.get(getApiUrl("padrones/cronicos/visita/:visitId/control"), () => HttpResponse.json(EMPTY_CONTROL)),
  http.get(getApiUrl("padrones/miembros"), () => HttpResponse.json({ members: [] })),
];
