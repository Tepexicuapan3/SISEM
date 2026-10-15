import { motivoCancelacionNotaAPI } from "@api/resources/catalogos/motivos-cancelacion-nota.api";
import type { MotivoCancelacionNotaListParams, MotivoCancelacionNotaListResponse } from "@api/types";
import { motivoCancelacionNotaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/motivos-cancelacion-nota.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useMotivoCancelacionNotaList = createCatalogListHook<
  MotivoCancelacionNotaListParams,
  MotivoCancelacionNotaListResponse
>({
  keys: motivoCancelacionNotaKeys,
  getAll: motivoCancelacionNotaAPI.getAll,
});
