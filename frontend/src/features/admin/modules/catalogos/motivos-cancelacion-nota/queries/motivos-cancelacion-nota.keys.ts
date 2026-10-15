import type { MotivoCancelacionNotaListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const motivoCancelacionNotaKeys = createCatalogKeys<MotivoCancelacionNotaListParams>([
  "admin",
  "catalogos",
  "motivos-cancelacion-nota",
]);
