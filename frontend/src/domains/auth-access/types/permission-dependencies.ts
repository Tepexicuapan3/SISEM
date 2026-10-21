const WRITE_ACTION = {
  CREATE: "create",
  UPDATE: "update",
  DELETE: "delete",
  MANAGE: "manage",
  ASSIGN: "assign",
  REVOKE: "revoke",
} as const;

const WRITE_ACTION_SET = new Set<string>(Object.values(WRITE_ACTION));

const EXPLICIT_PERMISSION_DEPENDENCIES = {
  "admin:gestion:usuarios:create": ["admin:gestion:roles:read"],
  "admin:gestion:usuarios:update": [
    "admin:gestion:roles:read",
    "admin:gestion:permisos:read",
  ],
  "admin:gestion:roles:create": ["admin:gestion:permisos:read"],
  "admin:gestion:roles:update": ["admin:gestion:permisos:read"],
} as const satisfies Record<string, readonly string[]>;

// Permisos de escritura cuyo `:read` hermano NO existe en el catalogo real:
// no se infiere dependencia (mirror de NO_INFERRED_READ_DEPENDENCY en
// backend/apps/authentication/services/permission_dependencies.py).
const NO_INFERRED_READ_DEPENDENCY = new Set<string>([
  "recepcion:fichas:medicina_general:create",
  "recepcion:fichas:especialidad:create",
  "recepcion:fichas:urgencias:create",
]);

const normalizePermission =(permissionCode: string) => permissionCode.trim();

const inferReadDependency = (permissionCode: string): string | null => {
  const segments = permissionCode.split(":").map((segment) => segment.trim());
  if (segments.length < 2) return null;

  const action = segments[segments.length - 1]?.toLowerCase();
  if (!action || !WRITE_ACTION_SET.has(action)) return null;

  const readSegments = [...segments];
  readSegments[readSegments.length - 1] = "read";
  return readSegments.join(":");
};

const getDirectDependencies = (permissionCode: string): string[] => {
  const normalizedPermission = normalizePermission(permissionCode);
  if (!normalizedPermission) return [];

  const explicitDependencies =
    EXPLICIT_PERMISSION_DEPENDENCIES[
      normalizedPermission as keyof typeof EXPLICIT_PERMISSION_DEPENDENCIES
    ] ?? [];

  const inferredDependency = NO_INFERRED_READ_DEPENDENCY.has(normalizedPermission)
    ? null
    : inferReadDependency(normalizedPermission);
  const dependencySet = new Set<string>(explicitDependencies);

  if (inferredDependency && inferredDependency !== normalizedPermission) {
    dependencySet.add(inferredDependency);
  }

  return Array.from(dependencySet).sort((first, second) =>
    first.localeCompare(second),
  );
};

export const getPermissionDependencyClosure = (
  permissionCode: string,
): string[] => {
  const normalizedPermission = normalizePermission(permissionCode);
  if (!normalizedPermission) return [];

  const visited = new Set<string>();
  const stack = [normalizedPermission];

  while (stack.length > 0) {
    const currentPermission = stack.pop();
    if (!currentPermission || visited.has(currentPermission)) continue;

    visited.add(currentPermission);

    const nextDependencies = getDirectDependencies(currentPermission);
    for (const dependency of nextDependencies) {
      if (!visited.has(dependency)) {
        stack.push(dependency);
      }
    }
  }

  return Array.from(visited).sort((first, second) =>
    first.localeCompare(second),
  );
};

export interface PermissionDependencyState {
  granted: boolean;
  requiredPermissions: string[];
  missingPermissions: string[];
}

export const evaluatePermissionDependencies = (
  permissionCode: string,
  grantedPermissions: readonly string[],
): PermissionDependencyState => {
  const normalizedPermission = normalizePermission(permissionCode);
  if (!normalizedPermission) {
    return {
      granted: false,
      requiredPermissions: [],
      missingPermissions: [],
    };
  }

  if (grantedPermissions.includes("*")) {
    return {
      granted: true,
      requiredPermissions: [normalizedPermission],
      missingPermissions: [],
    };
  }

  const requiredPermissions =
    getPermissionDependencyClosure(normalizedPermission);
  const missingPermissions = requiredPermissions.filter(
    (requiredPermission) => !grantedPermissions.includes(requiredPermission),
  );

  return {
    granted: missingPermissions.length === 0,
    requiredPermissions,
    missingPermissions,
  };
};

export interface PermissionRequirement {
  allOf?: readonly string[];
  anyOf?: readonly string[];
}

export interface PermissionRequirementState {
  granted: boolean;
  missingAllOf: string[];
  missingAnyOf: string[];
}

const mergeUnique = (values: readonly string[]) => {
  return Array.from(new Set(values)).sort((first, second) =>
    first.localeCompare(second),
  );
};

export const evaluatePermissionRequirement = (
  requirement: PermissionRequirement,
  grantedPermissions: readonly string[],
): PermissionRequirementState => {
  const allOfPermissions = requirement.allOf ?? [];
  const anyOfPermissions = requirement.anyOf ?? [];

  const allOfStates = allOfPermissions.map((permissionCode) =>
    evaluatePermissionDependencies(permissionCode, grantedPermissions),
  );
  const missingAllOf = mergeUnique(
    allOfStates.flatMap(
      (permissionState) => permissionState.missingPermissions,
    ),
  );

  const anyOfStates = anyOfPermissions.map((permissionCode) =>
    evaluatePermissionDependencies(permissionCode, grantedPermissions),
  );
  const hasAnyOf =
    anyOfStates.length === 0 ||
    anyOfStates.some((permissionState) => permissionState.granted);
  const missingAnyOf = hasAnyOf
    ? []
    : mergeUnique(
        anyOfStates.flatMap(
          (permissionState) => permissionState.requiredPermissions,
        ),
      );

  return {
    granted: missingAllOf.length === 0 && hasAnyOf,
    missingAllOf,
    missingAnyOf,
  };
};
