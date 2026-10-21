/**
 * Navigation Menu Types - Pure TypeScript interfaces
 *
 * @description Shape crudo (DTO) devuelto por `GET /api/v1/navigation-menu`.
 * El backend ya filtra el arbol por permisos efectivos del usuario
 * (RBACResolver) -- estos tipos representan la respuesta tal cual llega,
 * ANTES de mapearla a `NavigationSection`/`NavigationItem`
 * (ver `features/navigation/domain/mapNavigationMenu.ts`).
 *
 * `icon` viaja como string kebab-case (nombre logico, ej. "shield-user")
 * porque la BD (`cat_modulos.icono`) no conoce componentes de React.
 */

/** Fuente real de los datos. `"static"` significa flag OFF: el backend
 * responde arbol vacio y el frontend debe usar su fallback local. */
export type NavigationMenuSource = "db" | "static";

export interface NavigationMenuItemDTO {
  title: string;
  icon: string | null;
  url: string | null;
  badge: string | null;
  permissions: string[];
  items?: NavigationMenuItemDTO[];
}

export interface NavigationMenuSectionDTO {
  title: string;
  icon: string | null;
  permissions: string[];
  items: NavigationMenuItemDTO[];
}

/**
 * Response de `GET /api/v1/navigation-menu`.
 *
 * Con flag OFF (`source: "static"`) el backend responde
 * `{ source: "static", sections: [], secondaryItems: [] }` y el frontend
 * usa `NAV_CONFIG` local -- el backend NUNCA envia el fallback estatico.
 */
export interface NavigationMenuResponse {
  source: NavigationMenuSource;
  sections: NavigationMenuSectionDTO[];
  secondaryItems: NavigationMenuItemDTO[];
}

/**
 * Shape crudo (DTO) devuelto por `GET /api/v1/modules`.
 *
 * A diferencia de `NavigationMenuItemDTO`/`NavigationMenuSectionDTO`, este
 * arbol es PLANO (una sola lista raiz, sin split sections/secondaryItems) y
 * viene SIN filtrar por permisos del actor ni podar contenedores vacios: el
 * admin del catalogo de roles ve TODOS los nodos completos tal cual estan
 * modelados en BD. `items` siempre es un array (puede ser vacio), nunca
 * `undefined` -- a diferencia del arbol de navegacion.
 *
 * `id`/`orden`/`parentKey`/`isActive`/`isSystem` los agrego el backend en
 * `_serialize_module_node` (change `menu-modulos-crud-ui`, Fase 2) para
 * que la pantalla de gestion de menus (Fase 5) pueda editar/mover/ocultar
 * un nodo sin tener que resolver esos datos por otro lado -- la tab
 * "Permisos por modulo" del detalle de rol (`RolePermissionMatrixTab`) los ignora, solo
 * le importan `key`/`title`/`icon`/`permissions`/`items`.
 */
export interface ModuleCatalogNodeDTO {
  id: number;
  key: string;
  title: string;
  icon: string | null;
  url: string | null;
  orden: number;
  group: "primary" | "secondary";
  isSection: boolean;
  isSystem: boolean;
  isActive: boolean;
  parentKey: string | null;
  permissions: string[];
  items: ModuleCatalogNodeDTO[];
}

/** Response de `GET /api/v1/modules`. */
export interface ModuleCatalogResponse {
  modules: ModuleCatalogNodeDTO[];
}

/**
 * Params de `GET /api/v1/modules`.
 *
 * `includeInactive: true` suma los modulos ocultos (soft-deleted) al
 * arbol -- la pantalla de gestion de menus (Fase 5) lo necesita para poder
 * restaurarlos, y exige el permiso mas especifico
 * `admin:gestion:modulos:read` (a diferencia del modo default, que solo
 * pide `admin:gestion:roles:read` para la tab "Modulos" del detalle de
 * rol).
 */
export interface ModuleCatalogListParams {
  includeInactive?: boolean;
}

/**
 * Serializacion PLANA (sin hijos) de un `Modulo` -- misma forma en las 4
 * respuestas de escritura (create/update/hide/restore), ver
 * `serialize_module_summary` en el backend.
 */
export interface ModuleSummaryDTO {
  id: number;
  key: string;
  title: string;
  icon: string | null;
  url: string | null;
  badge: string | null;
  orden: number;
  group: "primary" | "secondary";
  isSection: boolean;
  isSystem: boolean;
  isActive: boolean;
  parentKey: string | null;
  permissions: string[];
}

/**
 * `POST /api/v1/modules`.
 *
 * `clave` NUNCA se envia -- el backend la deriva del titulo + padre en el
 * servidor (autoridad de la unicidad), con sufijo anti-colision automatico
 * (ver `CreateModuleUseCase._derive_key`). `deriveModuleKey.ts` en el
 * frontend replica el mismo algoritmo SOLO para mostrar un preview en el
 * wizard -- nunca se manda al backend.
 */
export interface CreateModuleRequest {
  title: string;
  icon?: string | null;
  url?: string | null;
  badge?: string | null;
  parentKey?: string | null;
  isSection?: boolean;
  group?: "primary" | "secondary";
  permissionCodes?: string[];
}

export interface CreateModuleResponse {
  key: string;
  id: number;
}

/**
 * `PATCH /api/v1/modules/{clave}`.
 *
 * Todos los campos son opcionales (solo se actualiza lo presente en el
 * payload). `parentKey` es especial: si viaja en el payload (incluso
 * `null`, que significa "mover a raiz"), la view ADEMAS dispara
 * `MoveModuleUseCase` en la misma transaccion -- ver
 * `UpdateModuleView.patch`.
 */
export interface UpdateModuleRequest {
  title?: string;
  icon?: string | null;
  url?: string | null;
  badge?: string | null;
  group?: "primary" | "secondary";
  isSection?: boolean;
  permissionCodes?: string[];
  parentKey?: string | null;
}

export interface UpdateModuleResponse {
  module: ModuleSummaryDTO;
}

/**
 * `PATCH /api/v1/modules/{clave}/visibility`.
 *
 * `isActive: false` oculta (soft delete); `isActive: true` restaura. Un
 * solo endpoint para ambas direcciones -- ver `ModuleVisibilityView`.
 */
export interface SetModuleVisibilityRequest {
  isActive: boolean;
}

export interface SetModuleVisibilityResponse {
  module: ModuleSummaryDTO;
}

/**
 * `PATCH /api/v1/modules/reorder`.
 *
 * Renumera TODO el grupo de hermanos de `parentKey` (10, 20, 30...):
 * `orderedKeys` debe coincidir EXACTAMENTE (mismo set) con los hermanos
 * activos actuales de ese padre, o el backend responde `VALIDATION_ERROR`.
 * `parentKey: null` reordena las secciones raiz.
 */
export interface ReorderModulesRequest {
  parentKey: string | null;
  orderedKeys: string[];
}

export interface ReorderModulesResultItem {
  key: string;
  orden: number;
}

export interface ReorderModulesResponse {
  modules: ReorderModulesResultItem[];
}
