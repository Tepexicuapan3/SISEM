import type { MotivoCancelacionCirugiaListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const motivoCancelacionCirugiaKeys = createCatalogKeys<MotivoCancelacionCirugiaListParams>([
  "admin",
  "catalogos",
  "motivos-cancelacion-cirugia",
]);
