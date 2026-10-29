import { useQuery } from "@tanstack/react-query";
import { legacyConsultationAPI } from "@api/resources/legacy-consultation.api";

export const legacyConsultationsKeys = {
  list: (noExp: string, pkNum: number, base?: string) =>
    ["expedientes", "legacy-consultations", noExp, pkNum, base ?? null] as const,
};

/**
 * Sin `base`: trae la lista de bases (años) con notas y las notas de la más
 * reciente. Con `base`: solo las notas de esa base.
 */
export const useLegacyConsultationsHistory = (
  noExp: string,
  pkNum = 0,
  enabled = true,
  base?: string,
) => {
  return useQuery({
    queryKey: legacyConsultationsKeys.list(noExp, pkNum, base),
    queryFn: () => legacyConsultationAPI.getForPatient(noExp, pkNum, base),
    enabled: enabled && Boolean(noExp),
    staleTime: 60 * 1000,
  });
};
