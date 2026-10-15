import { useQuery } from "@tanstack/react-query";
import { noteCancellationAPI } from "@api/resources/note-cancellation.api";

export const noteCancellationKeys = {
  preview: (visitId: number) =>
    ["expedientes", "note-cancellation-preview", visitId] as const,
};

export const useNoteCancellationPreview = (visitId: number, enabled = true) => {
  return useQuery({
    queryKey: noteCancellationKeys.preview(visitId),
    queryFn: () => noteCancellationAPI.getPreview(visitId),
    enabled: enabled && Boolean(visitId),
    // El estado de la nota cambia por fuera (farmacia, RH): nunca servir cache.
    staleTime: 0,
    gcTime: 0,
  });
};
