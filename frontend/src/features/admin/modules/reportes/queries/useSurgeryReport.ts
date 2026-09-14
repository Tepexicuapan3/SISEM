import { useQuery } from "@tanstack/react-query";
import { cirugiasReportAPI } from "@api/resources/reportes/cirugias.api";
import type { SurgeryReportParams } from "@api/types";

export function useSurgeryReport(
  params: SurgeryReportParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["admin", "reportes", "cirugias", params],
    queryFn: () => cirugiasReportAPI.getAll(params),
    enabled: options.enabled ?? true,
  });
}
