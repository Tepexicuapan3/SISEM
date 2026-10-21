import { faker } from "@faker-js/faker";
import type { Permission } from "@api/types/permissions.types";
import type { UserOverride } from "@api/types/users.types";

export const createMockPermission = (
  overrides: Partial<Permission> = {},
): Permission => {
  const group = faker.helpers.arrayElement([
    "admin",
    "clinico",
    "recepcion",
    "farmacia",
    "urgencias",
  ]);
  const moduleName = faker.helpers.arrayElement([
    "gestion",
    "catalogos",
    "consultas",
    "expedientes",
    "fichas",
  ]);
  const submodule = faker.helpers.arrayElement([
    "usuarios",
    "roles",
    "areas",
    "medicina_general",
    "especialidad",
  ]);
  const action = faker.helpers.arrayElement([
    "create",
    "read",
    "update",
    "delete",
  ]);
  const code = `${group}:${moduleName}:${submodule}:${action}`;

  return {
    id: faker.number.int({ min: 1, max: 200 }),
    code,
    description: `Permite ${action} ${submodule}`,
    isSystem: true,
    dependsOn:
      action === "read"
        ? []
        : [`${group}:${moduleName}:${submodule}:read`],
    ...overrides,
  };
};

export const createMockUserOverride = (
  overrides: Partial<UserOverride> = {},
): UserOverride => {
  const permission = createMockPermission();

  return {
    id: faker.number.int({ min: 1, max: 1000 }),
    permissionCode: permission.code,
    permissionDescription: permission.description,
    effect: faker.datatype.boolean() ? "ALLOW" : "DENY",
    expiresAt: faker.datatype.boolean()
      ? faker.date.future().toISOString()
      : null,
    isExpired: false,
    assignedAt: faker.date.recent().toISOString(),
    assignedBy: {
      id: faker.number.int({ min: 1, max: 1000 }),
      name: faker.person.fullName(),
    },
    ...overrides,
  };
};
