import { clasificacionCirugiaAPI } from "@api/resources/catalogos/clasificaciones-cirugia.api";
import type { ClasificacionCirugiaListParams, ClasificacionCirugiaListResponse } from "@api/types";
import { clasificacionCirugiaKeys } from "@features/admin/modules/catalogos/clasificaciones-cirugia/queries/clasificaciones-cirugia.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useClasificacionCirugiaList = createCatalogListHook<
  ClasificacionCirugiaListParams,
  ClasificacionCirugiaListResponse
>({
  keys: clasificacionCirugiaKeys,
  getAll: clasificacionCirugiaAPI.getAll,
});
