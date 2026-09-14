import { cie9McAPI } from "@api/resources/catalogos/cie9-mc.api";
import type { Cie9McListParams, Cie9McListResponse } from "@api/types";
import { cie9McKeys } from "@features/admin/modules/catalogos/cie9-mc/queries/cie9-mc.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useCie9McList = createCatalogListHook<
  Cie9McListParams,
  Cie9McListResponse
>({
  keys: cie9McKeys,
  getAll: cie9McAPI.getAll,
});
