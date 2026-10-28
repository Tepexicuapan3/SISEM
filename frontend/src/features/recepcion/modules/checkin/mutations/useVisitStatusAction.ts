import { useMutation, useQueryClient } from "@tanstack/react-query";
import { visitsAPI } from "@api/resources/visits.api";
import type { RecepcionStatusAction } from "@api/types";
import { visitFlowKeys } from "@features/recepcion/shared/queries/visit-flow.keys";

interface VisitStatusActionInput {
  visitId: number;
  targetStatus: RecepcionStatusAction;
  /** Solo se envia cuando `targetStatus` es "cancelada" -- el backend exige
   * el motivo tipificado para esa transicion (VISIT_MOTIVO_REQUERIDO) e
   * ignora los campos para las demas. */
  motivoCancelacionId?: number;
  motivoDetalle?: string;
}

export const useVisitStatusAction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ visitId, targetStatus, motivoCancelacionId, motivoDetalle }: VisitStatusActionInput) =>
      visitsAPI.updateStatus(visitId, { targetStatus, motivoCancelacionId, motivoDetalle }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: visitFlowKeys.lists() });
    },
  });
};
