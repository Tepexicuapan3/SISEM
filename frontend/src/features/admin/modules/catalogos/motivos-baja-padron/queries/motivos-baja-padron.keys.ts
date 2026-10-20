import type { MotivoBajaPadronListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const motivoBajaPadronKeys = createCatalogKeys<MotivoBajaPadronListParams>([
  "admin",
  "catalogos",
  "motivos-baja-padron",
]);
