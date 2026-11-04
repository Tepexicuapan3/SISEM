import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import type { AdscritosParams } from "@api/types";

const KEYS = {
  resumen: ["admin", "reportes", "adscripcion", "resumen"] as const,
  adscritos: (params: AdscritosParams) => ["admin", "reportes", "adscripcion", "adscritos", params] as const,
};

/** Conteos por centro, consultorio y turno de todos los centros del alcance del usuario. */
export function useAdscripcionResumen(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: KEYS.resumen,
    queryFn: () => adscripcionAPI.getReporteResumen(),
    enabled: options.enabled ?? true,
  });
}

/** Detalle paginado de adscritos (cada consulta queda auditada en el backend). */
export function useAdscritosReport(params: AdscritosParams, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: KEYS.adscritos(params),
    queryFn: () => adscripcionAPI.getReporteAdscritos(params),
    enabled: options.enabled ?? true,
    placeholderData: keepPreviousData,
  });
}
