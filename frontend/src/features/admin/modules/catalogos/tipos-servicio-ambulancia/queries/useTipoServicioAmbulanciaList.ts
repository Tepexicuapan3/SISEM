import { tipoServicioAmbulanciaAPI } from "@api/resources/catalogos/tipos-servicio-ambulancia.api";
import type { TipoServicioAmbulanciaListParams, TipoServicioAmbulanciaListResponse } from "@api/types";
import { tipoServicioAmbulanciaKeys } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/tipos-servicio-ambulancia.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useTipoServicioAmbulanciaList = createCatalogListHook<
  TipoServicioAmbulanciaListParams,
  TipoServicioAmbulanciaListResponse
>({
  keys: tipoServicioAmbulanciaKeys,
  getAll: tipoServicioAmbulanciaAPI.getAll,
});
