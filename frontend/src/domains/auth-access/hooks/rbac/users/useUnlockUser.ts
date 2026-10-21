import { useMutation } from "@tanstack/react-query";
import { usersAPI } from "@api/resources/users.api";

interface UnlockUserPayload {
  userId: number;
}

/**
 * Desbloquea el login de una cuenta bloqueada por intentos fallidos.
 *
 * No toca el cache del listado: el bloqueo no se muestra en la tabla. El
 * feedback (toast) lo maneja el componente que llama a `mutateAsync`.
 */
export const useUnlockUser = () => {
  return useMutation({
    mutationFn: ({ userId }: UnlockUserPayload) => usersAPI.unlock(userId),
  });
};
