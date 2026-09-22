import { useMutation, useQueryClient } from "@tanstack/react-query";
import { dispensacionFarmaciaAPI } from "@api/resources/farmacia/dispensacion.api";
import type { DispensePrescriptionRequest } from "@api/types";
import { dispensacionKeys } from "../queries/dispensacion.keys";

interface DispenseArgs {
  prescriptionId: number;
  data: DispensePrescriptionRequest;
}

export function useDispensePrescription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ prescriptionId, data }: DispenseArgs) =>
      dispensacionFarmaciaAPI.dispense(prescriptionId, data),
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({ queryKey: dispensacionKeys.queue() });
      void queryClient.invalidateQueries({ queryKey: dispensacionKeys.preview(variables.prescriptionId) });
    },
  });
}
