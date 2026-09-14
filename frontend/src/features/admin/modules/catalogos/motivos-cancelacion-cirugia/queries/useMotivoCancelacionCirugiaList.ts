import { motivoCancelacionCirugiaAPI } from "@api/resources/catalogos/motivos-cancelacion-cirugia.api";
import type { MotivoCancelacionCirugiaListParams, MotivoCancelacionCirugiaListResponse } from "@api/types";
import { motivoCancelacionCirugiaKeys } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/motivos-cancelacion-cirugia.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useMotivoCancelacionCirugiaList = createCatalogListHook<
  MotivoCancelacionCirugiaListParams,
  MotivoCancelacionCirugiaListResponse
>({
  keys: motivoCancelacionCirugiaKeys,
  getAll: motivoCancelacionCirugiaAPI.getAll,
});
