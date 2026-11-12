import type { MedicamentosListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const medicamentosKeys = createCatalogKeys<MedicamentosListParams>([
  "admin",
  "catalogos",
  "medicamentos",
]);
