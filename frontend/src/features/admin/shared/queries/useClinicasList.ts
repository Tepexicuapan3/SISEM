import { useQuery } from "@tanstack/react-query";
import { clinicasAPI } from "@api/resources/clinicas.api";

export function useClinicasList(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["clinicas", "list"],
    queryFn: () => clinicasAPI.getAll(),
    staleTime: 5 * 60 * 1000,
    enabled: options.enabled ?? true,
  });
}
