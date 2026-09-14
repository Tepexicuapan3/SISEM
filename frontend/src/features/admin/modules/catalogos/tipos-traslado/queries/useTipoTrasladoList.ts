import { tipoTrasladoAPI } from "@api/resources/catalogos/tipos-traslado.api";
import type { TipoTrasladoListParams, TipoTrasladoListResponse } from "@api/types";
import { tipoTrasladoKeys } from "@features/admin/modules/catalogos/tipos-traslado/queries/tipos-traslado.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useTipoTrasladoList = createCatalogListHook<
  TipoTrasladoListParams,
  TipoTrasladoListResponse
>({
  keys: tipoTrasladoKeys,
  getAll: tipoTrasladoAPI.getAll,
});
