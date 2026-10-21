import { http, HttpResponse, delay } from "msw";
import { getApiUrl } from "../urls";
import type { Permission } from "@api/types/permissions.types";
import { getMockSessionUser, hasMockPermission } from "../session";
import {
  getRolePermissions,
  roleExistsById,
  setRolePermissions,
} from "./roles";
import { createMockRolePermission } from "../../factories/roles";

const MOCK_DELAY = {
  list: 700,
  detail: 450,
  mutate: 400,
};

const baseCatalog: Array<Omit<Permission, "dependsOn">> = [
  {
    id: 1,
    code: "admin:gestion:usuarios:read",
    description: "Ver usuarios",
    isSystem: true,
  },
  {
    id: 2,
    code: "admin:gestion:usuarios:create",
    description: "Crear usuarios",
    isSystem: true,
  },
  {
    id: 3,
    code: "admin:gestion:usuarios:update",
    description: "Editar usuarios",
    isSystem: true,
  },
  {
    id: 4,
    code: "admin:gestion:usuarios:delete",
    description: "Eliminar usuarios",
    isSystem: true,
  },
  {
    id: 5,
    code: "admin:gestion:roles:read",
    description: "Ver roles",
    isSystem: true,
  },
  {
    id: 6,
    code: "admin:gestion:roles:create",
    description: "Crear roles",
    isSystem: true,
  },
  {
    id: 7,
    code: "admin:gestion:roles:update",
    description: "Gestionar roles",
    isSystem: true,
  },
  {
    id: 8,
    code: "admin:gestion:roles:delete",
    description: "Eliminar roles",
    isSystem: true,
  },
  {
    id: 9,
    code: "admin:gestion:permisos:read",
    description: "Ver permisos",
    isSystem: true,
  },
  {
    id: 10,
    code: "admin:catalogos:centros_atencion:read",
    description: "Ver centros de atencion",
    isSystem: true,
  },
  {
    id: 11,
    code: "admin:catalogos:areas:read",
    description: "Ver areas",
    isSystem: true,
  },
  {
    id: 16,
    code: "admin:catalogos:areas:create",
    description: "Crear areas",
    isSystem: true,
  },
  {
    id: 17,
    code: "admin:catalogos:areas:update",
    description: "Editar areas",
    isSystem: true,
  },
  {
    id: 18,
    code: "admin:catalogos:areas:delete",
    description: "Eliminar areas",
    isSystem: true,
  },
  {
    id: 19,
    code: "admin:catalogos:centros_atencion:create",
    description: "Crear centros de atencion",
    isSystem: true,
  },
  {
    id: 20,
    code: "admin:catalogos:centros_atencion:update",
    description: "Editar centros de atencion",
    isSystem: true,
  },
  {
    id: 21,
    code: "admin:catalogos:centros_atencion:delete",
    description: "Eliminar centros de atencion",
    isSystem: true,
  },
  {
    id: 12,
    code: "admin:reportes:read",
    description: "Ver reportes",
    isSystem: true,
  },
  {
    id: 13,
    code: "clinico:consultas:read",
    description: "Ver consultas",
    isSystem: true,
  },
  {
    id: 14,
    code: "clinico:consultas:create",
    description: "Crear consultas",
    isSystem: true,
  },
  {
    id: 15,
    code: "recepcion:fichas:medicina_general:create",
    description: "Generar ficha de medicina general",
    isSystem: true,
  },
];

/**
 * Espejo simplificado de `get_permission_direct_dependencies` (backend):
 * dependencias explicitas + `X:read` inferido para acciones de escritura,
 * siempre que ese `read` exista en el catalogo (las fichas `:create` no
 * infieren read). El mock emite `dependsOn` igual que `GET /permissions`.
 */
const WRITE_ACTIONS = new Set([
  "create",
  "update",
  "delete",
  "manage",
  "assign",
  "revoke",
]);
const EXPLICIT_DEPENDENCIES: Record<string, string[]> = {
  "admin:gestion:usuarios:update": [
    "admin:gestion:roles:read",
    "admin:gestion:permisos:read",
  ],
};

const buildDependsOn = (code: string): string[] => {
  const segments = code.split(":");
  const action = segments[segments.length - 1];
  const inferred =
    segments.length > 1 && WRITE_ACTIONS.has(action)
      ? [`${segments.slice(0, -1).join(":")}:read`]
      : [];
  const known = new Set(baseCatalog.map((permission) => permission.code));

  return [...new Set([...(EXPLICIT_DEPENDENCIES[code] ?? []), ...inferred])]
    .filter((dependency) => known.has(dependency))
    .sort();
};

export const permissionsCatalog: Permission[] = baseCatalog.map(
  (permission) => ({
    ...permission,
    dependsOn: buildDependsOn(permission.code),
  }),
);

const requirePermission = (permission: string) => {
  const sessionUser = getMockSessionUser();

  if (!sessionUser) {
    return HttpResponse.json(
      {
        code: "SESSION_EXPIRED",
        message: "Debes iniciar sesion para realizar esta accion.",
      },
      { status: 401 },
    );
  }

  if (!hasMockPermission(permission)) {
    return HttpResponse.json(
      {
        code: "PERMISSION_DENIED",
        message: `No tienes permiso para realizar esta accion (${permission}).`,
      },
      { status: 403 },
    );
  }

  return null;
};

const toRolePermission = (permission: Permission) =>
  createMockRolePermission({
    id: permission.id,
    code: permission.code,
    description: permission.description,
  });

const normalizeRolePermissionSet = (permissionIds: number[]) => {
  const selectedPermissions = permissionsCatalog.filter((permission) =>
    permissionIds.includes(permission.id),
  );

  const selectedCodes = new Set(
    selectedPermissions.map((permission) => permission.code),
  );
  const writeActions = new Set(["create", "update", "delete"]);

  for (const permission of selectedPermissions) {
    const parts = permission.code.split(":");
    const action = parts[3];

    if (!writeActions.has(action ?? "")) continue;

    const readCode = `${parts[0]}:${parts[1]}:${parts[2]}:read`;
    const readPermission = permissionsCatalog.find(
      (catalogPermission) => catalogPermission.code === readCode,
    );

    if (!readPermission) continue;
    selectedCodes.add(readPermission.code);
  }

  const normalizedPermissions = permissionsCatalog.filter((permission) =>
    selectedCodes.has(permission.code),
  );

  normalizedPermissions.sort((first, second) =>
    first.code.localeCompare(second.code),
  );

  return normalizedPermissions.map(toRolePermission);
};

const canRemovePermission = (
  permissionToRemove: Permission,
  nextPermissions: Permission[],
) => {
  const parts = permissionToRemove.code.split(":");
  const action = parts[3];
  if (action !== "read") return true;

  return !nextPermissions.some((permission) => {
    const permissionParts = permission.code.split(":");
    const sameResource =
      permissionParts[0] === parts[0] &&
      permissionParts[1] === parts[1] &&
      permissionParts[2] === parts[2];
    const writeAction = ["create", "update", "delete"].includes(
      permissionParts[3] ?? "",
    );
    return sameResource && writeAction;
  });
};

export const permissionsHandlers = [
  http.get(getApiUrl("permissions"), async () => {
    await delay(MOCK_DELAY.list);
    const permissionError = requirePermission("admin:gestion:permisos:read");
    if (permissionError) return permissionError;

    return HttpResponse.json({
      items: permissionsCatalog,
      total: permissionsCatalog.length,
    });
  }),

  http.get(getApiUrl("permissions/categories"), async () => {
    await delay(MOCK_DELAY.detail);
    const permissionError = requirePermission("admin:gestion:permisos:read");
    if (permissionError) return permissionError;

    return HttpResponse.json([
      "GESTION",
      "CATALOGOS",
      "REPORTES",
      "CLINICO",
      "RECEPCION",
    ]);
  }),

  http.post(getApiUrl("permissions/assign"), async ({ request }) => {
    await delay(MOCK_DELAY.mutate);
    const permissionError = requirePermission("admin:gestion:roles:update");
    if (permissionError) return permissionError;

    const body = (await request.json()) as {
      roleId?: number;
      role_id?: number;
      permissionIds?: number[];
      permission_ids?: number[];
    };

    const roleId = Number(body.roleId ?? body.role_id);
    const permissionIds = body.permissionIds ?? body.permission_ids ?? [];

    if (!Number.isFinite(roleId)) {
      return HttpResponse.json(
        {
          code: "VALIDATION_ERROR",
          message: "Revisa los datos capturados.",
          details: {
            roleId: ["Rol requerido"],
          },
        },
        { status: 400 },
      );
    }

    if (!roleExistsById(roleId)) {
      return HttpResponse.json(
        {
          code: "ROLE_NOT_FOUND",
          message: "Rol no encontrado",
        },
        { status: 404 },
      );
    }

    const validIds = new Set(
      permissionsCatalog.map((permission) => permission.id),
    );
    const invalidPermissionId = permissionIds.find((id) => !validIds.has(id));

    if (invalidPermissionId !== undefined) {
      return HttpResponse.json(
        {
          code: "PERMISSION_NOT_FOUND",
          message: "Permiso no encontrado",
        },
        { status: 404 },
      );
    }

    const normalizedPermissions = normalizeRolePermissionSet(permissionIds);
    setRolePermissions(roleId, normalizedPermissions);

    return HttpResponse.json({
      roleId,
      permissions: normalizedPermissions,
    });
  }),

  http.delete(
    getApiUrl("permissions/roles/:roleId/permissions/:permissionId"),
    async ({ params }) => {
      await delay(MOCK_DELAY.detail);
      const permissionError = requirePermission("admin:gestion:roles:update");
      if (permissionError) return permissionError;

      const roleId = Number(params.roleId);
      const permissionId = Number(params.permissionId);

      if (!roleExistsById(roleId)) {
        return HttpResponse.json(
          {
            code: "ROLE_NOT_FOUND",
            message: "Rol no encontrado",
          },
          { status: 404 },
        );
      }

      const currentPermissions = getRolePermissions(roleId);
      const nextPermissions = currentPermissions.filter(
        (permission) => permission.id !== permissionId,
      );

      if (nextPermissions.length === currentPermissions.length) {
        return HttpResponse.json(
          {
            code: "PERMISSION_NOT_FOUND",
            message: "Permiso no encontrado",
          },
          { status: 404 },
        );
      }

      const removedPermission = permissionsCatalog.find(
        (permission) => permission.id === permissionId,
      );

      const nextPermissionEntities = permissionsCatalog.filter((permission) =>
        nextPermissions.some(
          (rolePermission) => rolePermission.id === permission.id,
        ),
      );

      if (
        removedPermission &&
        !canRemovePermission(removedPermission, nextPermissionEntities)
      ) {
        return HttpResponse.json(
          {
            code: "PERMISSION_DEPENDENCY",
            message:
              "No puedes revocar :read mientras existan permisos de escritura del mismo recurso.",
          },
          { status: 400 },
        );
      }

      setRolePermissions(roleId, nextPermissions);

      return HttpResponse.json({ roleId, permissions: nextPermissions });
    },
  ),
];
