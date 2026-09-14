import type { Cie9McListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const cie9McKeys = createCatalogKeys<Cie9McListParams>([
  "admin",
  "catalogos",
  "cie9-mc",
]);
