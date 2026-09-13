import { useQuery } from "@tanstack/react-query";
import { consultasDiarioReportAPI } from "@api/resources/reportes/consultasDiario.api";
import type { DailyConsultationReportParams } from "@api/types";

export function useDailyConsultationReport(
  params: DailyConsultationReportParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["admin", "reportes", "consultas-diario", params],
    queryFn: () => consultasDiarioReportAPI.getAll(params),
    enabled: options.enabled ?? true,
  });
}
