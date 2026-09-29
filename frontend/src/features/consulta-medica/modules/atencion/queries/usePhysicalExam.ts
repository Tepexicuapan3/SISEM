import { useQuery } from "@tanstack/react-query";
import { clinicalCatalogsAPI, physicalExamAPI } from "@api/resources/unified-history.api";

export const physicalExamKeys = {
  detail: (visitId: number) => ["consulta-medica", "physical-exam", visitId] as const,
  catalogs: ["consulta-medica", "clinical-catalogs"] as const,
};

export const usePhysicalExam = (visitId: number, enabled: boolean) =>
  useQuery({
    queryKey: physicalExamKeys.detail(visitId),
    queryFn: () => physicalExamAPI.get(visitId),
    enabled,
  });

export const useBodyRegions = (enabled: boolean) =>
  useQuery({
    queryKey: physicalExamKeys.catalogs,
    queryFn: () => clinicalCatalogsAPI.get(),
    enabled,
    staleTime: 30 * 60 * 1000,
    select: (catalogs) => catalogs.bodyRegions,
  });
