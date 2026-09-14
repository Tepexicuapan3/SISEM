import { useQuery } from "@tanstack/react-query";
import { incapacidadesReportAPI } from "@api/resources/reportes/incapacidades.api";
import type { MedicalLeaveReportParams } from "@api/types";

export function useMedicalLeaveReport(
  params: MedicalLeaveReportParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["admin", "reportes", "incapacidades", params],
    queryFn: () => incapacidadesReportAPI.getAll(params),
    enabled: options.enabled ?? true,
  });
}
