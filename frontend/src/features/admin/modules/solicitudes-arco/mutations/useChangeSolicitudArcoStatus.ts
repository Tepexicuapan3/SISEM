import { useMutation, useQueryClient } from "@tanstack/react-query";
import { arcoAPI } from "@api/resources/arco.api";
import type { ChangeArcoRequestStatusPayload } from "@api/types";
import { ARCO_QUERY_KEY } from "@features/admin/modules/solicitudes-arco/queries/useSolicitudesArco";

export function useChangeSolicitudArcoStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ChangeArcoRequestStatusPayload }) =>
      arcoAPI.changeStatus(id, data),
    onSettled: () => {
      // onSettled (no onSuccess): ante un 409 por carrera con otro usuario
      // tambien hay que refrescar para mostrar el estatus real.
      void queryClient.invalidateQueries({ queryKey: [ARCO_QUERY_KEY] });
    },
  });
}
