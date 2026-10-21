import { useMutation } from "@tanstack/react-query";
import { usersAPI } from "@api/resources/users.api";

interface ForceLogoutUserPayload {
  userId: number;
}

/**
 * Fuerza el cierre de sesion de otro usuario.
 *
 * No toca el cache del listado: la accion no cambia ningun dato visible de la
 * tabla. El feedback (toast) lo maneja el componente que llama a `mutateAsync`.
 */
export const useForceLogoutUser = () => {
  return useMutation({
    mutationFn: ({ userId }: ForceLogoutUserPayload) =>
      usersAPI.forceLogout(userId),
  });
};
