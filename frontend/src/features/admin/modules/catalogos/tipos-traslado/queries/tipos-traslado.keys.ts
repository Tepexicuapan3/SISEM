import type { TipoTrasladoListParams } from "@api/types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

export const tipoTrasladoKeys = createCatalogKeys<TipoTrasladoListParams>([
  "admin",
  "catalogos",
  "tipos-traslado",
]);
