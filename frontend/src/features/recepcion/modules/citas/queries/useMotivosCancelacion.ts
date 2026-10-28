import { useQuery } from "@tanstack/react-query";
import { citasAPI } from "@api/resources/citas.api";
import { CITAS_KEYS } from "@features/recepcion/modules/citas/queries/useCitasList";

/** Motivos tipificados para cancelar una cita o una ficha (catálogo MotivoCita). */
export const useMotivosCancelacion = (options?: { enabled?: boolean }) =>
  useQuery({
    queryKey: CITAS_KEYS.motivosCancelacion,
    queryFn:  () => citasAPI.getMotivosCancelacion(),
    staleTime: 5 * 60_000,
    enabled:   options?.enabled ?? true,
  });
