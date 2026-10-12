import { faker } from "@faker-js/faker";
import type { AuthUser } from "@api/types/auth.types";
import type {
  UserDetail,
  UserListItem,
  UserRole,
} from "@api/types/users.types";
import { createMockCentroAtencionRef } from "@/test/factories/centros-atencion";

export const createMockAuthUser = (
  overrides: Partial<AuthUser> = {},
): AuthUser => {
  const firstName = faker.person.firstName();
  const paternalName = faker.person.lastName();
  const maternalName = faker.person.lastName();
  const fullName = `${firstName} ${paternalName} ${maternalName}`;
  const mustChangePassword = overrides.mustChangePassword ?? false;
  const requiresOnboarding = overrides.requiresOnboarding ?? mustChangePassword;
  const permissions = overrides.permissions ?? ["*"];
  const effectivePermissions = overrides.effectivePermissions ?? permissions;
  const capabilities = overrides.capabilities ?? {};
  const permissionDependenciesVersion =
    overrides.permissionDependenciesVersion ?? "v1";
  const strictCapabilityPrefixes = overrides.strictCapabilityPrefixes ?? [
    "flow.recepcion.",
    "flow.somatometria.",
    "flow.visits.",
  ];
  const authRevision =
    overrides.authRevision ?? faker.date.recent().toISOString();
  const avatarUrl =
    overrides.avatarUrl !== undefined
      ? overrides.avatarUrl
      : faker.datatype.boolean()
        ? faker.image.avatar()
        : null;

  return {
    id: overrides.id ?? faker.number.int({ min: 1, max: 1000 }),
    username:
      overrides.username ??
      faker.internet.username({ firstName, lastName: paternalName }),
    fullName: overrides.fullName ?? fullName,
    email:
      overrides.email ??
      faker.internet.email({ firstName, lastName: paternalName }),
    avatarUrl,
    primaryRole: overrides.primaryRole ?? "ADMIN",
    landingRoute: overrides.landingRoute ?? "/dashboard",
    roles: overrides.roles ?? ["ADMIN", "CLINICO"],
    permissions,
    effectivePermissions,
    capabilities,
    permissionDependenciesVersion,
    strictCapabilityPrefixes,
    authRevision,
    mustChangePassword,
    requiresOnboarding,
  };
};

type MockUserListItem = UserListItem & { avatarUrl?: string | null };

const USER_ROLE_POOL = [
  "Admin",
  "Clinico",
  "Recepcion",
  "Farmacia",
  "Urgencias",
  "Auditoria",
  "Soporte",
] as const;

export const createMockUser = (
  overrides: Partial<MockUserListItem> = {},
): MockUserListItem => {
  const firstName = faker.person.firstName();
  const paternalName = faker.person.lastName();
  const maternalName = faker.person.lastName();
  const fullname = `${firstName} ${paternalName} ${maternalName}`;
  const clinic =
    overrides.clinic !== undefined
      ? overrides.clinic
      : faker.datatype.boolean()
        ? createMockCentroAtencionRef()
        : null;
  const avatarUrl =
    overrides.avatarUrl !== undefined
      ? overrides.avatarUrl
      : faker.datatype.boolean()
        ? faker.image.avatar()
        : null;
  const termsAccepted = overrides.termsAccepted ?? true;
  const mustChangePassword = overrides.mustChangePassword ?? false;

  return {
    id: faker.number.int({ min: 1, max: 1000 }),
    username: faker.internet.username({ firstName, lastName: paternalName }),
    fullname,
    email: faker.internet.email({ firstName, lastName: paternalName }),
    clinic,
    areaClinica: null,
    cdLaboral: null,
    telefono: null,
    sexo: null,
    fechaNac: null,
    escolaridad: null,
    escuela: null,
    tipoPersonal: null,
    cedulas: [],
    primaryRole: faker.helpers.arrayElement(USER_ROLE_POOL),
    isActive: faker.datatype.boolean(),
    termsAccepted,
    mustChangePassword,
    avatarUrl,
    ...overrides,
  };
};

export const createMockUserDetail = (
  overrides: Partial<UserDetail> = {},
): UserDetail => {
  const baseUser = createMockUser(overrides);
  const firstName = faker.person.firstName();
  const paternalName = faker.person.lastName();
  const maternalName = faker.person.lastName();

  return {
    ...baseUser,
    firstName,
    paternalName,
    maternalName,
    noExp: null,
    termsAccepted: true,
    mustChangePassword: false,
    lastLoginAt: faker.date.recent().toISOString(),
    lastIp: faker.internet.ipv4(),
    createdAt: faker.date.past().toISOString(),
    createdBy: {
      id: faker.number.int({ min: 1, max: 1000 }),
      name: faker.person.fullName(),
    },
    updatedAt: null,
    updatedBy: null,
    ...overrides,
  };
};

export const createMockUserRole = (
  overrides: Partial<UserRole> = {},
): UserRole => {
  return {
    id: faker.number.int({ min: 1, max: 20 }),
    name: "Clinico",
    description: "Clinico General",
    isPrimary: false,
    assignedAt: faker.date.recent().toISOString(),
    assignedBy: {
      id: faker.number.int({ min: 1, max: 1000 }),
      name: faker.person.fullName(),
    },
    ...overrides,
  };
};
