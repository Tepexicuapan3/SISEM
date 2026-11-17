import {
  ciesAPI,
  type CiesListParams,
  type CiesListResponse,
} from "@api/resources/catalogos/cies.api";
import { ciesKeys } from "@features/admin/modules/catalogos/cies/queries/cies.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useCiesList = createCatalogListHook<
  CiesListParams,
  CiesListResponse
>({
  keys: ciesKeys,
  getAll: ciesAPI.getAll,
});
