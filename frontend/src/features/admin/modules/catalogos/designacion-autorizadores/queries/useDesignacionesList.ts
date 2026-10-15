import { authorizerDesignationsAPI } from "@api/resources/catalogos/authorizer-designations.api";
import type { DesignacionesListParams, DesignacionesListResponse } from "@api/types";
import { designacionKeys } from "@features/admin/modules/catalogos/designacion-autorizadores/queries/designacion.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useDesignacionesList = createCatalogListHook<
  DesignacionesListParams,
  DesignacionesListResponse
>({
  keys: designacionKeys,
  getAll: authorizerDesignationsAPI.getAll,
});
