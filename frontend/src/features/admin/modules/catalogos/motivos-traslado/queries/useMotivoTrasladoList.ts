import { motivoTrasladoAPI } from "@api/resources/catalogos/motivos-traslado.api";
import type { MotivoTrasladoListParams, MotivoTrasladoListResponse } from "@api/types";
import { motivoTrasladoKeys } from "@features/admin/modules/catalogos/motivos-traslado/queries/motivos-traslado.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useMotivoTrasladoList = createCatalogListHook<
  MotivoTrasladoListParams,
  MotivoTrasladoListResponse
>({
  keys: motivoTrasladoKeys,
  getAll: motivoTrasladoAPI.getAll,
});
