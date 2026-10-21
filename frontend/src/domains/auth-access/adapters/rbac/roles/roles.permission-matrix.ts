import type { ModuleCatalogNodeDTO, Permission } from "@api/types";
import {
  buildPermissionModuleIndex,
  type ModuleRef,
} from "@/domains/auth-access/adapters/rbac/roles/roles.module-tree";

/**
 * Mapper puro (sin React) de la matriz "Permisos por modulo".
 *
 * Convierte el catalogo de permisos (`GET /permissions`, con `dependsOn`)
 * y el arbol de modulos (`GET /modules`) en filas (modulo, recurso) x
 * acciones. Todo es data-driven: nada de codigos hardcodeados salvo
 * `OWNER_OVERRIDES`, que solo desempata que modulo "es dueno" de un recurso
 * compartido.
 */

// =============================================================================
// TIPOS
// =============================================================================

/** Acciones con columna propia; el resto va a "Otras". */
export type MatrixAction = "read" | "create" | "update" | "delete";

export const MATRIX_ACTIONS: readonly MatrixAction[] = [
  "read",
  "create",
  "update",
  "delete",
];

export interface ParsedPermissionCode {
  code: string;
  /** Todo el codigo menos el ultimo segmento (ej. `recepcion:fichas:urgencias`). */
  resource: string;
  /** Ultimo segmento en minusculas (ej. `create`). */
  action: string;
}

export interface MatrixCell {
  code: string;
  id: number;
  action: string;
  /** El codigo esta enlazado a mas de un modulo (tildarlo afecta a otros). */
  isShared: boolean;
  /** Los OTROS modulos que enlazan este codigo. */
  sharedWith: ModuleRef[];
}

export interface MatrixRow {
  /** `${module.key}|${resource}` */
  key: string;
  module: ModuleRef;
  resource: string;
  depth: number;
  isOwner: boolean;
  cells: Partial<Record<MatrixAction, MatrixCell>>;
  /** Acciones fuera de read/create/update/delete. */
  other: MatrixCell[];
}

export interface ResourceGroup {
  key: string;
  title: string;
  rows: MatrixRow[];
}

export interface PermissionMatrix {
  groups: ResourceGroup[];
  /** Recursos sin modulo + codigos malformados: seccion "Otros permisos". */
  orphans: MatrixCell[];
}

export interface DependencyIndex {
  /** codigo -> dependencias DIRECTAS (pueden incluir codigos fuera del catalogo). */
  deps: Map<string, string[]>;
}

// =============================================================================
// PARSEO
// =============================================================================

/**
 * Parser propio: `parsePermissionCode` de `permission-hierarchy.ts` es lossy
 * para codigos de 5 segmentos (`recepcion:fichas:medicina_general:create`).
 *
 * Devuelve `null` si el codigo es malformado: sin ":" o con algun segmento
 * vacio (ej. `flow.recepcion.queue.write`).
 */
export const parseCode = (rawCode: string): ParsedPermissionCode | null => {
  const code = rawCode.trim();
  if (!code.includes(":")) return null;

  const segments = code.split(":");
  if (segments.some((segment) => segment.trim() === "")) return null;

  const action = segments[segments.length - 1].trim().toLowerCase();
  const resource = segments.slice(0, -1).join(":");
  return { code, resource, action };
};

/** Acciones que el backend infiere como dependientes de `:read`
 * (espejo de `WRITE_ACTIONS` en `permission_dependencies.py`). */
const WRITE_ACTIONS = new Set([
  "create",
  "update",
  "delete",
  "manage",
  "assign",
  "revoke",
]);

/** Escrituras cuyo `:read` hermano no existe en el catalogo: no se infiere
 * (espejo de `NO_INFERRED_READ_DEPENDENCY` del backend y de
 * `domains/auth-access/types/permission-dependencies.ts`). */
const NO_INFERRED_READ_DEPENDENCY = new Set([
  "recepcion:fichas:medicina_general:create",
  "recepcion:fichas:especialidad:create",
  "recepcion:fichas:urgencias:create",
]);

// =============================================================================
// DEPENDENCIAS
// =============================================================================

/**
 * Indice codigo -> dependencias directas. Usa `dependsOn` del backend; solo
 * cuando falta (backend viejo) infiere `X:read` para acciones de escritura.
 */
export const buildDependencyIndex = (catalog: Permission[]): DependencyIndex => {
  const deps = new Map<string, string[]>();

  for (const permission of catalog) {
    if (Array.isArray(permission.dependsOn)) {
      deps.set(permission.code, permission.dependsOn);
      continue;
    }

    const parsed = parseCode(permission.code);
    deps.set(
      permission.code,
      parsed &&
        WRITE_ACTIONS.has(parsed.action) &&
        !NO_INFERRED_READ_DEPENDENCY.has(parsed.code)
        ? [`${parsed.resource}:read`]
        : [],
    );
  }

  return { deps };
};

/**
 * Cierre transitivo (incluye los codigos de entrada). DFS con `visited`:
 * tolera ciclos. Puede incluir codigos que no existen en el catalogo; el
 * caller los filtra con `isInCatalog`/`resolveCodesToIds`.
 */
export const getDependencyClosure = (
  codes: Iterable<string>,
  index: DependencyIndex,
): Set<string> => {
  const visited = new Set<string>();
  const stack = [...codes];

  while (stack.length > 0) {
    const current = stack.pop() as string;
    if (visited.has(current)) continue;
    visited.add(current);
    for (const dependency of index.deps.get(current) ?? []) {
      if (!visited.has(dependency)) stack.push(dependency);
    }
  }

  return visited;
};

/** Dependencias (del cierre) que no existen en el catalogo. */
export const getMissingDependencies = (
  code: string,
  index: DependencyIndex,
): string[] =>
  [...getDependencyClosure([code], index)].filter(
    (dependency) => !index.deps.has(dependency),
  );

/**
 * Codigos del draft que dependen (transitivamente) de alguno de `removed`
 * y por lo tanto quedarian huerfanos al quitarlo. No incluye a `removed`.
 */
export const getReverseDependents = (
  removed: Set<string>,
  draftCodes: Set<string>,
  index: DependencyIndex,
): Set<string> => {
  const dependents = new Set<string>();

  for (const code of draftCodes) {
    if (removed.has(code)) continue;
    const closure = getDependencyClosure([code], index);
    for (const target of removed) {
      if (target !== code && closure.has(target)) {
        dependents.add(code);
        break;
      }
    }
  }

  return dependents;
};

/** Traduce codigos a ids con el catalogo; los inexistentes van a `missingCodes`. */
export const resolveCodesToIds = (
  codes: Iterable<string>,
  catalog: Permission[],
): { ids: number[]; missingCodes: string[] } => {
  const codeToId = new Map(catalog.map((permission) => [permission.code, permission.id]));
  const ids: number[] = [];
  const missingCodes: string[] = [];

  for (const code of codes) {
    const id = codeToId.get(code);
    if (id === undefined) missingCodes.push(code);
    else ids.push(id);
  }

  return { ids, missingCodes };
};

// =============================================================================
// PLAN DE TOGGLE (cascadas)
// =============================================================================

/** recurso -> codigos del catalogo de ese recurso (solo codigos bien formados). */
export const buildResourceIndex = (catalog: Permission[]): Map<string, string[]> => {
  const index = new Map<string, string[]>();
  for (const permission of catalog) {
    const parsed = parseCode(permission.code);
    if (!parsed) continue;
    const list = index.get(parsed.resource);
    if (list) list.push(permission.code);
    else index.set(parsed.resource, [permission.code]);
  }
  return index;
};

export interface TogglePlan {
  /** Codigos a agregar al draft (incluye el pedido si faltaba). */
  add: string[];
  /** Codigos a quitar del draft (incluye el pedido si estaba). */
  remove: string[];
}

interface PlanContext {
  draftCodes: Set<string>;
  dependencyIndex: DependencyIndex;
  resourceIndex: Map<string, string[]>;
}

/**
 * Calcula el efecto de tildar/destildar UN codigo:
 * - tildar: el cierre de dependencias + el `:read` del recurso (auto-Ver);
 * - destildar: si es `:read`, todo el recurso; ademas los dependientes que
 *   quedarian sin su dependencia (cascada, con punto fijo).
 * Solo devuelve cambios reales respecto de `draftCodes`.
 */
export const planToggle = (
  code: string,
  checked: boolean,
  context: PlanContext,
): TogglePlan => {
  const { draftCodes, dependencyIndex, resourceIndex } = context;

  if (checked) {
    const wanted = getDependencyClosure([code], dependencyIndex);
    const parsed = parseCode(code);
    if (parsed) {
      const readCode = `${parsed.resource}:read`;
      if (dependencyIndex.deps.has(readCode)) {
        for (const dependency of getDependencyClosure([readCode], dependencyIndex)) {
          wanted.add(dependency);
        }
      }
    }
    const add = [...wanted].filter(
      (candidate) => dependencyIndex.deps.has(candidate) && !draftCodes.has(candidate),
    );
    return { add, remove: [] };
  }

  const removed = new Set<string>([code]);
  const expandRead = (target: string) => {
    const parsed = parseCode(target);
    if (parsed?.action !== "read") return;
    for (const sibling of resourceIndex.get(parsed.resource) ?? []) {
      if (draftCodes.has(sibling)) removed.add(sibling);
    }
  };

  expandRead(code);
  let size = -1;
  while (size !== removed.size) {
    size = removed.size;
    for (const dependent of getReverseDependents(removed, draftCodes, dependencyIndex)) {
      removed.add(dependent);
    }
    for (const target of [...removed]) expandRead(target);
  }

  return { add: [], remove: [...removed].filter((target) => draftCodes.has(target)) };
};

/** Aplica `planToggle` a varios codigos en secuencia sobre un draft simulado. */
export const planBatchToggle = (
  codes: string[],
  checked: boolean,
  context: PlanContext,
): TogglePlan => {
  const simulated = new Set(context.draftCodes);
  const add = new Set<string>();
  const remove = new Set<string>();

  for (const code of codes) {
    const plan = planToggle(code, checked, { ...context, draftCodes: simulated });
    for (const target of plan.add) {
      simulated.add(target);
      add.add(target);
      remove.delete(target);
    }
    for (const target of plan.remove) {
      simulated.delete(target);
      remove.add(target);
      add.delete(target);
    }
  }

  return { add: [...add], remove: [...remove] };
};

// =============================================================================
// DUENO DE RECURSO
// =============================================================================

/**
 * Overrides explicitos recurso -> clave de modulo dueno, para los recursos
 * compartidos donde la heuristica de tokens no alcanza. La clave se busca
 * por recurso exacto y luego por prefijo mas largo (`recepcion:fichas`
 * cubre `recepcion:fichas:urgencias`, etc.).
 */
export const OWNER_OVERRIDES: Record<string, string> = {
  "clinico:consultas": "clinico.consultas.bandeja",
  "clinico:somatometria": "clinico.somatometria",
  "recepcion:fichas": "recepcion.fichas",
  "clinico:ambulancias": "clinico.ambulancias",
  "clinico:cirugias": "clinico.cirugias",
};

const resolveOverride = (resource: string): string | null => {
  const segments = resource.split(":");
  for (let length = segments.length; length > 0; length -= 1) {
    const override = OWNER_OVERRIDES[segments.slice(0, length).join(":")];
    if (override) return override;
  }
  return null;
};

const tokenize = (value: string): Set<string> =>
  new Set(value.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean));

const countOverlap = (resource: string, moduleKey: string): number => {
  const resourceTokens = tokenize(resource);
  let overlap = 0;
  for (const token of tokenize(moduleKey)) {
    if (resourceTokens.has(token)) overlap += 1;
  }
  return overlap;
};

// =============================================================================
// CONSTRUCCION DE LA MATRIZ
// =============================================================================

interface FlatModule {
  node: ModuleCatalogNodeDTO;
  depth: number;
  rootKey: string;
  rootTitle: string;
}

const flattenTree = (tree: ModuleCatalogNodeDTO[]): FlatModule[] => {
  const flat: FlatModule[] = [];
  const visit = (node: ModuleCatalogNodeDTO, depth: number, root: ModuleCatalogNodeDTO) => {
    flat.push({ node, depth, rootKey: root.key, rootTitle: root.title });
    for (const child of node.items) visit(child, depth + 1, root);
  };
  for (const root of tree) visit(root, 0, root);
  return flat;
};

export const buildPermissionMatrix = (
  tree: ModuleCatalogNodeDTO[],
  catalog: Permission[],
): PermissionMatrix => {
  const moduleIndex = buildPermissionModuleIndex(tree);
  const flat = flattenTree(tree);

  // recurso -> (codigo -> permiso); malformados a orphans.
  const resources = new Map<string, Permission[]>();
  const malformed: Permission[] = [];
  for (const permission of catalog) {
    const parsed = parseCode(permission.code);
    if (!parsed) {
      malformed.push(permission);
      continue;
    }
    const list = resources.get(parsed.resource);
    if (list) list.push(permission);
    else resources.set(parsed.resource, [permission]);
  }

  const buildCell = (permission: Permission, ownerKey: string | null): MatrixCell => {
    const refs = moduleIndex.get(permission.code) ?? [];
    const sharedWith = refs.filter((ref) => ref.key !== ownerKey);
    return {
      code: permission.code,
      id: permission.id,
      action: parseCode(permission.code)?.action ?? permission.code,
      isShared: refs.length > 1,
      sharedWith,
    };
  };

  const rowsByModule = new Map<string, MatrixRow[]>();
  const orphans: MatrixCell[] = malformed.map((permission) => buildCell(permission, null));

  const addCell = (row: MatrixRow, cell: MatrixCell) => {
    if ((MATRIX_ACTIONS as readonly string[]).includes(cell.action)) {
      row.cells[cell.action as MatrixAction] = cell;
    } else {
      row.other.push(cell);
    }
  };

  const sortedResources = [...resources.entries()].sort(([a], [b]) => a.localeCompare(b));

  for (const [resource, permissions] of sortedResources) {
    const codes = new Set(permissions.map((permission) => permission.code));
    const candidates = flat.filter(({ node }) =>
      node.permissions.some((code) => codes.has(code)),
    );

    if (candidates.length === 0) {
      for (const permission of permissions) orphans.push(buildCell(permission, null));
      continue;
    }

    const overrideKey = resolveOverride(resource);
    const overridden = overrideKey
      ? candidates.find(({ node }) => node.key === overrideKey)
      : undefined;

    const linkedCount = (candidate: FlatModule) =>
      candidate.node.permissions.filter((code) => codes.has(code)).length;

    const owner =
      overridden ??
      [...candidates].sort(
        (a, b) =>
          countOverlap(resource, b.node.key) - countOverlap(resource, a.node.key) ||
          linkedCount(b) - linkedCount(a) ||
          a.depth - b.depth ||
          a.node.key.localeCompare(b.node.key),
      )[0];

    for (const candidate of candidates) {
      const isOwner = candidate === owner;
      const row: MatrixRow = {
        key: `${candidate.node.key}|${resource}`,
        module: { key: candidate.node.key, title: candidate.node.title },
        resource,
        depth: candidate.depth,
        isOwner,
        cells: {},
        other: [],
      };

      const rowPermissions = isOwner
        ? permissions
        : permissions.filter(({ code }) => candidate.node.permissions.includes(code));
      for (const permission of rowPermissions) {
        addCell(row, buildCell(permission, candidate.node.key));
      }
      row.other.sort((a, b) => a.code.localeCompare(b.code));

      const list = rowsByModule.get(candidate.node.key);
      if (list) list.push(row);
      else rowsByModule.set(candidate.node.key, [row]);
    }
  }

  const groupsByRoot = new Map<string, ResourceGroup>();
  for (const { node, rootKey, rootTitle } of flat) {
    const rows = rowsByModule.get(node.key);
    if (!rows) continue;
    let group = groupsByRoot.get(rootKey);
    if (!group) {
      group = { key: rootKey, title: rootTitle, rows: [] };
      groupsByRoot.set(rootKey, group);
    }
    group.rows.push(...rows);
  }

  orphans.sort((a, b) => a.code.localeCompare(b.code));

  return { groups: [...groupsByRoot.values()], orphans };
};

// =============================================================================
// ETIQUETAS
// =============================================================================

const ACTION_LABELS: Record<MatrixAction, string> = {
  read: "Ver",
  create: "Crear",
  update: "Editar",
  delete: "Eliminar",
};

/** Etiqueta en espanol de una accion (`read` -> "Ver"); el resto se capitaliza. */
export const getActionLabel = (action: string): string => {
  const known = ACTION_LABELS[action as MatrixAction];
  if (known) return known;
  const spaced = action.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

/** Nombre legible de un recurso: ultimo segmento sin guiones bajos
 * (`recepcion:fichas:medicina_general` -> "medicina general"). */
export const formatResourceLabel = (resource: string): string =>
  (resource.split(":").pop() ?? resource).replace(/_/g, " ");
