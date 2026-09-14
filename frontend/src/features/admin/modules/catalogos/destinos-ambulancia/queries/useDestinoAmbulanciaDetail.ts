import { useQuery } from "@tanstack/react-query";
import { destinoAmbulanciaAPI } from "@api/resources/catalogos/destinos-ambulancia.api";
import type { DestinoAmbulanciaDetailResponse } from "@api/types";
import { destinoAmbulanciaKeys } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/destinos-ambulancia.keys";

export const useDestinoAmbulanciaDetail = (id?: number, enabled = true) => {
  const isEnabled = enabled && Boolean(id);

  return useQuery<DestinoAmbulanciaDetailResponse>({
    queryKey: destinoAmbulanciaKeys.detail(id!),
    queryFn: () => {
      if (!id) throw new Error("id es requerido");
      return destinoAmbulanciaAPI.getById(id);
    },
    enabled: isEnabled,
    staleTime: 60 * 1000,
  });
};
