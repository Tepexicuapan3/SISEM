import { useQuery } from "@tanstack/react-query";
import { prescriptionAuthorizationsAPI } from "@api/resources/prescription-authorizations.api";

export function usePendingPrescriptionAuthorizations(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["prescription-authorizations", "pending"],
    queryFn: () => prescriptionAuthorizationsAPI.getPending(),
    enabled: options.enabled ?? true,
  });
}
