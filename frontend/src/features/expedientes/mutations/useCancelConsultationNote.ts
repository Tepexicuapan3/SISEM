import { useMutation, useQueryClient } from "@tanstack/react-query";
import { noteCancellationAPI } from "@api/resources/note-cancellation.api";
import type { CancelConsultationNoteRequest } from "@api/types";
import { NOTE_CANCELLATION_INVALIDATION_PREFIXES } from "@features/expedientes/domain/note-cancellation";
import { noteCancellationKeys } from "@features/expedientes/queries/useNoteCancellationPreview";

interface Payload {
  visitId: number;
  data: CancelConsultationNoteRequest;
}

/**
 * Cancela en cascada una nota cerrada. No reintenta ni guarda la contrasena.
 * Invalida historial, incapacidades, estudios, receta y el preview.
 */
export const useCancelConsultationNote = () => {
  const queryClient = useQueryClient();

  const invalidate = (visitId: number) => {
    for (const queryKey of NOTE_CANCELLATION_INVALIDATION_PREFIXES) {
      void queryClient.invalidateQueries({ queryKey: [...queryKey] });
    }
    void queryClient.invalidateQueries({
      queryKey: ["doctor-consultation", "prescription-items", visitId],
    });
    void queryClient.invalidateQueries({
      queryKey: noteCancellationKeys.preview(visitId),
    });
  };

  return useMutation({
    mutationFn: ({ visitId, data }: Payload) =>
      noteCancellationAPI.cancel(visitId, data),
    retry: false,
    onSuccess: (_result, variables) => invalidate(variables.visitId),
    // 409 (bloqueo/estado cambiado): el preview que vio el usuario quedo viejo.
    onError: (_error, variables) => {
      void queryClient.invalidateQueries({
        queryKey: noteCancellationKeys.preview(variables.visitId),
      });
    },
  });
};
