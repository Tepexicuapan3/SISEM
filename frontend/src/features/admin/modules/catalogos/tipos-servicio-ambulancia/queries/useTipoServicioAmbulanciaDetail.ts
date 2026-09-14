import { useQuery } from "@tanstack/react-query";
import { tipoServicioAmbulanciaAPI } from "@api/resources/catalogos/tipos-servicio-ambulancia.api";
import type { TipoServicioAmbulanciaDetailResponse } from "@api/types";
import { tipoServicioAmbulanciaKeys } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/tipos-servicio-ambulancia.keys";

export const useTipoServicioAmbulanciaDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<TipoServicioAmbulanciaDetailResponse>({
    queryKey: tipoServicioAmbulanciaKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return tipoServicioAmbulanciaAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
