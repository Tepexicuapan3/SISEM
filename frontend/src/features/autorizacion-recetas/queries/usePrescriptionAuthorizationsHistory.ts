import { useQuery } from "@tanstack/react-query";
import { prescriptionAuthorizationsAPI } from "@api/resources/prescription-authorizations.api";
import type { PrescriptionAuthorizationHistoryParams } from "@api/types";

export function usePrescriptionAuthorizationsHistory(
  params: PrescriptionAuthorizationHistoryParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["prescription-authorizations", "history", params],
    queryFn: () => prescriptionAuthorizationsAPI.getHistory(params),
    enabled: options.enabled ?? true,
  });
}
