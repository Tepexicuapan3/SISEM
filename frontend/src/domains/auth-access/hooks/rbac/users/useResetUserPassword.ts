import { useMutation } from "@tanstack/react-query";
import { usersAPI } from "@api/resources/users.api";

interface ResetUserPasswordPayload {
  userId: number;
  sendEmail?: boolean;
}

/**
 * Restablece la contraseña de un usuario existente.
 *
 * A diferencia de useActivateUser/useDeactivateUser, esta mutación NO
 * sincroniza cache ni muestra un toast genérico en onSuccess: el resultado
 * (contraseña temporal en texto plano) debe mostrarse en un modal dedicado
 * que el componente que llama a `mutateAsync` es responsable de abrir.
 * La invalidación del listado de usuarios ocurre recién al cerrar ese modal
 * (ver UserDetailsSecurityTab.tsx), no acá.
 */
export const useResetUserPassword = () => {
  return useMutation({
    mutationFn: ({ userId, sendEmail }: ResetUserPasswordPayload) =>
      usersAPI.resetPassword(userId, { sendEmail }),
  });
};
