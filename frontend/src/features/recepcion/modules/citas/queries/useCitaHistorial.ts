import { useQuery } from "@tanstack/react-query";
import { citasAPI } from "@api/resources/citas.api";
import type { CitaHistorialItem } from "@api/types";
import { CITAS_KEYS } from "./useCitasList";

export const useCitaHistorial = (citaId: number, enabled: boolean) =>
  useQuery<CitaHistorialItem[]>({
    queryKey: [...CITAS_KEYS.all, "historial", citaId] as const,
    queryFn: async () => (await citasAPI.getHistorial(citaId)).items,
    staleTime: 30_000,
    enabled,
  });
