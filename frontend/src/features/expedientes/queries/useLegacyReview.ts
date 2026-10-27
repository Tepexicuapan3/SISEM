import { useQuery } from "@tanstack/react-query";
import { legacyConsultationAPI } from "@api/resources/legacy-consultation.api";

export const legacyReviewKeys = {
  list: (noExp: string, pkNum: number) => ["expedientes", "legacy-review", noExp, pkNum] as const,
};

export const useLegacyReview = (noExp: string, pkNum = 0, enabled = true) => {
  return useQuery({
    queryKey: legacyReviewKeys.list(noExp, pkNum),
    queryFn: () => legacyConsultationAPI.getReview(noExp, pkNum),
    enabled: enabled && Boolean(noExp),
    staleTime: 60 * 1000,
  });
};
