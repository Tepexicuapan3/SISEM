import { useMutation, useQueryClient } from "@tanstack/react-query";
import { solicitudesAPI } from "@api/resources/autorizaciones/solicitudes.api";
import type {
  DecisionRequest,
  NotificarRequest,
  NotificarResponse,
  SolicitudDetalleResponse,
} from "@api/types/autorizaciones/solicitudes.types";
import { solicitudKeys } from "@features/autorizaciones/queries/useSolicitudes";

/** Exito o error, se recarga: si falla por version vieja o ya resuelta, la pantalla muestra lo actual. */
const useRecargarSolicitudes = () => {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: solicitudKeys.all });
    void queryClient.invalidateQueries({ queryKey: ["notificaciones"] });
  };
};

export const useDecidirSolicitud = () => {
  const recargar = useRecargarSolicitudes();
  return useMutation<SolicitudDetalleResponse, Error, { uuid: string; data: DecisionRequest }>({
    mutationFn: ({ uuid, data }) => solicitudesAPI.decidir(uuid, data),
    onSettled: recargar,
  });
};

export const useNotificarSolicitud = () => {
  const recargar = useRecargarSolicitudes();
  return useMutation<NotificarResponse, Error, { uuid: string; data: NotificarRequest }>({
    mutationFn: ({ uuid, data }) => solicitudesAPI.notificar(uuid, data),
    onSettled: recargar,
  });
};
