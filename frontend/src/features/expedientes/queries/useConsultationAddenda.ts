import { useQuery } from "@tanstack/react-query";
import { consultationAddendumAPI } from "@api/resources/consultation-addendum.api";

export const consultationAddendaKeys = {
  list: (visitId: number) => ["expedientes", "consultation-addenda", visitId] as const,
};

export const useConsultationAddenda = (visitId: number, enabled = true) => {
  return useQuery({
    queryKey: consultationAddendaKeys.list(visitId),
    queryFn: () => consultationAddendumAPI.getAll(visitId),
    enabled: enabled && Boolean(visitId),
  });
};
