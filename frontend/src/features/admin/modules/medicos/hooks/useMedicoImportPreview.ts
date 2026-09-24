import { useMutation } from "@tanstack/react-query";
import { medicosAPI } from "@api/resources/medicos.api";
import type { MedicoImportResult } from "@api/types/medicos.types";

interface MedicoImportPreviewInput {
  file: File;
}

/**
 * PASO 1 - Preview de importación masiva de médicos: valida el Excel sin
 * persistir nada.
 */
export const useMedicoImportPreview = () => {
  return useMutation<MedicoImportResult, Error, MedicoImportPreviewInput>({
    mutationFn: ({ file }) => medicosAPI.import.preview(file),
  });
};
