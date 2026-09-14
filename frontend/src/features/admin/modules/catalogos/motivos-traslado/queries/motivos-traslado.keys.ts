import type { MotivoTrasladoListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const motivoTrasladoKeys = createCatalogKeys<MotivoTrasladoListParams>([
  "admin",
  "catalogos",
  "motivos-traslado",
]);
