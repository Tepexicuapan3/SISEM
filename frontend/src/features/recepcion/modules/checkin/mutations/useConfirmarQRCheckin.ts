import { useMutation, useQueryClient } from "@tanstack/react-query";
import { citasAPI } from "@api/resources/citas.api";
import type { ConfirmarCheckinOptions } from "@api/types";
import { visitFlowKeys } from "@features/recepcion/shared/queries/visit-flow.keys";

/**
 * Confirma el check-in: re-envía el mismo payload crudo del QR (el backend
 * re-valida la firma HMAC, nunca confía en un folio suelto) y crea el Visit.
 * Mismo patrón de invalidación que `useCreateVisit` — el check-in por QR crea
 * una visita igual que el check-in manual, así que las mismas colas deben
 * refrescarse.
 */
export const useConfirmarQRCheckin = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ payload, ...options }: { payload: string } & ConfirmarCheckinOptions) =>
      citasAPI.confirmarVerificacionQR(payload, options),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: visitFlowKeys.lists() });
      queryClient.invalidateQueries({ queryKey: ["agenda-semanal"] });
    },
  });
};
