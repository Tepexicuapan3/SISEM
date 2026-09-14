import { useQuery } from "@tanstack/react-query";
import { legacyConsultationAPI } from "@api/resources/legacy-consultation.api";

export const legacyConsultationsKeys = {
  list: (noExp: string, pkNum: number) =>
    ["expedientes", "legacy-consultations", noExp, pkNum] as const,
};

export const useLegacyConsultationsHistory = (noExp: string, pkNum = 0, enabled = true) => {
  return useQuery({
    queryKey: legacyConsultationsKeys.list(noExp, pkNum),
    queryFn: () => legacyConsultationAPI.getForPatient(noExp, pkNum),
    enabled: enabled && Boolean(noExp),
    staleTime: 60 * 1000,
  });
};
