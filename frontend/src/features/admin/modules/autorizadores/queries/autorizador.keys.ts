import type { AutorizadoresListParams } from "@api/types/autorizaciones/autorizadores.types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

const base = createCatalogKeys<AutorizadoresListParams>(["admin", "autorizadores"]);

export const autorizadorKeys = {
  ...base,
  historial: (id: number) => [...base.all, "historial", id] as const,
  usuariosElegibles: (search: string) => [...base.all, "usuarios-elegibles", search] as const,
  catalogos: () => [...base.all, "catalogos"] as const,
};
