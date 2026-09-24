import { useMutation, useQueryClient } from "@tanstack/react-query";
import { medicosAPI } from "@api/resources/medicos.api";
import type { MedicoImportResult } from "@api/types/medicos.types";

interface MedicoImportConfirmInput {
  file: File;
}

// Mismo query key raíz que `keys.all` en
// `features/admin/modules/medicos/hooks/useMedicos.ts` (privado a ese
// módulo, no exportado -- se duplica el literal en vez de exportarlo,
// fuera de alcance de este change).
const MEDICOS_LIST_QUERY_KEY = ["medicos"] as const;

/**
 * PASO 2 - Confirm de importación masiva de médicos: crea médicos solo si
 * el archivo no tiene ningún error (todo-o-nada). Invalida el listado de
 * médicos cuando la importación efectivamente inserta registros.
 */
export const useMedicoImportConfirm = () => {
  const queryClient = useQueryClient();

  return useMutation<MedicoImportResult, Error, MedicoImportConfirmInput>({
    mutationFn: ({ file }) => medicosAPI.import.confirm(file),
    onSuccess: (result) => {
      if (result.inserted > 0) {
        void queryClient.invalidateQueries({ queryKey: MEDICOS_LIST_QUERY_KEY });
      }
    },
  });
};
