import { useMutation, useQueryClient } from "@tanstack/react-query";
import { notificacionesAPI } from "@api/resources/notificaciones/notificaciones.api";
import { notificacionKeys } from "@features/notificaciones/queries/useNotificaciones";

const useInvalidar = () => {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: notificacionKeys.all });
};

export const useMarcarLeida = () => {
  const invalidar = useInvalidar();
  return useMutation({ mutationFn: (id: number) => notificacionesAPI.marcarLeida(id), onSuccess: invalidar });
};

export const useMarcarTodasLeidas = () => {
  const invalidar = useInvalidar();
  return useMutation({ mutationFn: () => notificacionesAPI.marcarTodasLeidas(), onSuccess: invalidar });
};
