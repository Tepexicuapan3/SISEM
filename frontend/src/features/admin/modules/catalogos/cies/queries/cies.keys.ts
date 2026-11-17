import type { CiesListParams } from "@api/resources/catalogos/cies.api";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const ciesKeys = createCatalogKeys<CiesListParams, string>([
  "admin",
  "catalogos",
  "cies",
]);
