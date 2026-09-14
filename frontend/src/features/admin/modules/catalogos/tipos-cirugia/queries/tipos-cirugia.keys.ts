import type { TipoCirugiaListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const tipoCirugiaKeys = createCatalogKeys<TipoCirugiaListParams>([
  "admin",
  "catalogos",
  "tipos-cirugia",
]);
