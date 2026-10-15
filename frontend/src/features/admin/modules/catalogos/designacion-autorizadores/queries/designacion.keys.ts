import type { DesignacionesListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const designacionKeys = createCatalogKeys<DesignacionesListParams>([
  "admin",
  "designacion-autorizadores",
]);
