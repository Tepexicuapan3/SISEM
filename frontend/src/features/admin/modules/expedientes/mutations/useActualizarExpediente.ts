import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { expedientesAPI } from "@api/resources/expedientes.api";
import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";
import { expedientesKeys } from "../queries/expedientes.keys";

// Codigos de ActualizarExpedienteView (backend, expediente_view.py).
const SYNC_ERROR_MESSAGES: Record<string, string> = {
  SYNC_EN_CURSO:
    "Este expediente ya se está actualizando en otra sesión. Espera a que termine y vuelve a intentar.",
  SYNC_ERROR:
    "No se pudo actualizar el expediente desde SERMED. No se aplicó ningún cambio.",
  PERMISSION_DENIED: "No tienes permiso para actualizar expedientes.",
  SESSION_EXPIRED: "Tu sesión expiró. Inicia sesión nuevamente.",
  NETWORK_ERROR: "No hay conexión con el servidor. Intenta nuevamente.",
};

export const useActualizarExpediente = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: expedientesAPI.actualizar,
    onSuccess: (resultado, variables) => {
      queryClient.invalidateQueries({
        queryKey: expedientesKeys.detail(variables.expediente),
      });
      if (resultado.estado === "PARCIAL") {
        toast.warning("Expediente actualizado parcialmente", {
          description:
            "Los datos de SERMED quedaron al día, pero no se pudieron actualizar los pacientes de SIRES. " +
            (resultado.errores[0] ?? ""),
        });
        return;
      }
      toast.success("Expediente sincronizado correctamente.");
    },
    onError: (error) => {
      toast.error("No se pudo actualizar el expediente", {
        description: getCatalogErrorMessage(
          error,
          "Error al sincronizar el expediente. Intenta nuevamente.",
          SYNC_ERROR_MESSAGES,
        ),
      });
    },
  });
};
