import { destinoAmbulanciaAPI } from "@api/resources/catalogos/destinos-ambulancia.api";
import type { DestinoAmbulanciaListParams, DestinoAmbulanciaListResponse } from "@api/types";
import { destinoAmbulanciaKeys } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/destinos-ambulancia.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useDestinoAmbulanciaList = createCatalogListHook<
  DestinoAmbulanciaListParams,
  DestinoAmbulanciaListResponse
>({
  keys: destinoAmbulanciaKeys,
  getAll: destinoAmbulanciaAPI.getAll,
});
