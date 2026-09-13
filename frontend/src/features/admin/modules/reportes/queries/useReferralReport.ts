import { useQuery } from "@tanstack/react-query";
import { pasesReportAPI } from "@api/resources/reportes/pases.api";
import type { ReferralReportParams } from "@api/types";

export function useReferralReport(
  params: ReferralReportParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["admin", "reportes", "pases", params],
    queryFn: () => pasesReportAPI.getAll(params),
    enabled: options.enabled ?? true,
  });
}
