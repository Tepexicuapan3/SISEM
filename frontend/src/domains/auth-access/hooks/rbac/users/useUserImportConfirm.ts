import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usersAPI } from "@api/resources/users.api";
import type { UserImportJob, UserImportResult } from "@api/types";
import { usersKeys } from "@/domains/auth-access/hooks/rbac/users/users.keys";

interface UserImportConfirmInput {
  file: File;
  /** Avance del import en segundo plano (fase y filas procesadas). */
  onProgress?: (job: UserImportJob) => void;
}

/**
 * PASO 2 - Confirm de importacion masiva: encola el import en el backend
 * (Celery) y espera a que termine consultando su avance. Crea usuarios solo
 * si el archivo no tiene ningun error (todo-o-nada). Invalida el listado de
 * usuarios cuando la importacion efectivamente inserta registros.
 */
export const useUserImportConfirm = () => {
  const queryClient = useQueryClient();

  return useMutation<UserImportResult, Error, UserImportConfirmInput>({
    mutationFn: ({ file, onProgress }) => usersAPI.import.confirm(file, { onProgress }),
    onSuccess: (result) => {
      if (result.inserted > 0) {
        void queryClient.invalidateQueries({ queryKey: usersKeys.list() });
      }
    },
  });
};
