import { useQuery } from "@tanstack/react-query";
import { ambulanciasReportAPI } from "@api/resources/reportes/ambulancias.api";
import type { AmbulanceReportParams } from "@api/types";

export function useAmbulanceReport(
  params: AmbulanceReportParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["admin", "reportes", "ambulancias", params],
    queryFn: () => ambulanciasReportAPI.getAll(params),
    enabled: options.enabled ?? true,
  });
}
