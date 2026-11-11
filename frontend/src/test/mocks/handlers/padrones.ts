import { http, HttpResponse } from "msw";
import type { ChronicVisitNotice } from "@api/types/padrones.types";
import { getApiUrl } from "../urls";

// Aviso de cronicos de la consulta: por defecto el paciente no esta en el
// padron (el aviso no se pinta). Las pruebas del aviso mockean el hook.
const EMPTY_NOTICE: ChronicVisitNotice = { enrollments: [], suggestion: null, canEnroll: false };

export const padronesHandlers = [
  http.get(getApiUrl("padrones/cronicos/visita/:visitId/aviso"), () => HttpResponse.json(EMPTY_NOTICE)),
];
