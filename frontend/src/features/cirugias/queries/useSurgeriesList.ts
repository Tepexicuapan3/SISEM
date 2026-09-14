import { useQuery } from "@tanstack/react-query";
import { cirugiasAPI } from "@api/resources/cirugias.api";
import type { SurgeryListParams } from "@api/types";

export function useSurgeriesList(
  params: SurgeryListParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["cirugias", "list", params],
    queryFn: () => cirugiasAPI.getAll(params),
    enabled: options.enabled ?? true,
  });
}
