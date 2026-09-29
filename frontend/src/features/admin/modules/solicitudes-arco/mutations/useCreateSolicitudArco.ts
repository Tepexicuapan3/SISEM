import { useMutation, useQueryClient } from "@tanstack/react-query";
import { arcoAPI } from "@api/resources/arco.api";
import type { CreateArcoRequestPayload } from "@api/types";
import { ARCO_QUERY_KEY } from "@features/admin/modules/solicitudes-arco/queries/useSolicitudesArco";

export function useCreateSolicitudArco() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateArcoRequestPayload) => arcoAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [ARCO_QUERY_KEY] });
    },
  });
}
