import { http, HttpResponse, delay } from "msw";
import {
  createMockUser,
  createMockUserDetail,
  createMockUserRole,
} from "../../factories/users";
import { createMockUserOverride } from "../../factories/permissions";
import { centrosAtencionDB } from "./centros-atencion";
import { getAvailableRoles } from "./roles";
import { permissionsCatalog } from "./permissions";
import { getApiUrl } from "../urls";
import { getMockSessionUser, hasMockPermission } from "../session";
import type {
  AddUserOverrideRequest,
  AssignRolesRequest,
  CreateUserRequest,
  SetPrimaryRoleRequest,
  UpdateUserRequest,
} from "@api/types/users.types";

const MOCK_DELAY = {
  list: 1200,
  detail: 900,
  mutate: 800,
  fast: 600,
};

// Base de datos de usuarios en memoria (100 usuarios)
// INYECTAMOS "PERSONAS" PARA TESTEO VISUAL DE UI/UX
const clinicRefs = centrosAtencionDB.map((center) => ({
  id: center.id,
  name: center.name,
}));

const getRandomClinic = () => {
  if (clinicRefs.length === 0 || Math.random() < 0.2) {
    return null;
  }
  const index = Math.floor(Math.random() * clinicRefs.length);
  return clinicRefs[index] ?? null;
};

const getMockLastLoginAt = (offset: number) => {
  return new Date(Date.now() - (offset + 1) * 36e5).toISOString();
};

const getMockLastIp = (offset: number) => {
  const segment = 10 + (offset % 200);
  const host = 20 + ((offset * 7) % 200);
  return `192.168.${segment}.${host}`;
};

const usersDB = [
  createMockUser({
    id: 1,
    username: "jperez",
    fullname: "JUAN PEREZ",
    email: "juan.perez@metro.cdmx.gob.mx",
    clinic: clinicRefs[0] ?? null,
    primaryRole: "Clinico",
    avatarUrl: "https://i.pravatar.cc/80?img=12",
    isActive: true,
  }),
  createMockUser({
    id: 2,
    username: "max_overflow",
    fullname: "MAXIMILIANO DE LOS SANTOS VON SCHWARZENBERG",
    email:
      "maximiliano.super.largo.email.corporativo.extremadamente.largo@metro.cdmx.gob.mx",
    clinic: clinicRefs[0] ?? null,
    primaryRole: "Admin",
    avatarUrl: "https://i.pravatar.cc/80?img=32",
    isActive: true,
    termsAccepted: false,
  }),
  createMockUser({
    id: 3,
    username: "banned_user",
    fullname: "ROBERTO BLOQUEADO",
    email: "banned_user@metro.cdmx.gob.mx",
    clinic: null,
    primaryRole: "Auditoria",
    avatarUrl: null,
    isActive: false,
    mustChangePassword: true,
  }),
  ...Array.from({ length: 97 }).map((_, i) =>
    createMockUser({ id: i + 4, clinic: getRandomClinic() }),
  ),
];

const buildUserProfile = (fullname: string) => {
  const [firstName = "", paternalName = "", maternalName = ""] =
    fullname.split(" ");
  return { firstName, paternalName, maternalName };
};

interface UserSecurityState {
  termsAccepted: boolean;
  mustChangePassword: boolean;
  lastLoginAt: string | null;
  lastIp: string | null;
}

const userProfilesDB = new Map(
  usersDB.map((user) => [user.id, buildUserProfile(user.fullname)]),
);

const userSecurityDB = new Map<number, UserSecurityState>(
  usersDB.map((user, index) => [
    user.id,
    {
      termsAccepted: user.termsAccepted ?? true,
      mustChangePassword: user.mustChangePassword ?? false,
      lastLoginAt: getMockLastLoginAt(index),
      lastIp: getMockLastIp(index),
    },
  ]),
);

const buildPrimaryRole = (user: (typeof usersDB)[number]) => {
  const primaryRole = user.primaryRole || "Clinico";
  const roleMatch = getAvailableRoles().find(
    (role) => role.name === primaryRole,
  );
  return createMockUserRole({
    id: roleMatch?.id,
    name: primaryRole,
    isPrimary: true,
  });
};

const userRolesDB = new Map(
  usersDB.map((user) => [user.id, [buildPrimaryRole(user)]]),
);

const userOverridesDB = new Map(
  usersDB.map((user) => [
    user.id,
    [] as ReturnType<typeof createMockUserOverride>[],
  ]),
);

userOverridesDB.set(1, [
  createMockUserOverride({
    permissionCode: "admin:gestion:usuarios:export",
    permissionDescription: "Exportar datos de usuarios",
    effect: "ALLOW",
  }),
  createMockUserOverride({
    permissionCode: "admin:gestion:facturacion:manage",
    permissionDescription: "Gestionar facturacion",
    effect: "DENY",
  }),
]);

const cloneUser = (user: (typeof usersDB)[number]) => ({
  ...user,
  clinic: user.clinic ? { ...user.clinic } : null,
});

const cloneUserProfile = (
  profile: ReturnType<typeof buildUserProfile>,
): ReturnType<typeof buildUserProfile> => ({ ...profile });

const cloneUserSecurity = (security: UserSecurityState): UserSecurityState => ({
  ...security,
});

const cloneUserRole = (role: ReturnType<typeof createMockUserRole>) => ({
  ...role,
  assignedBy: {
    ...role.assignedBy,
  },
});

const cloneUserOverride = (
  override: ReturnType<typeof createMockUserOverride>,
) => ({
  ...override,
  assignedBy: {
    ...override.assignedBy,
  },
});

const INITIAL_USERS = usersDB.map(cloneUser);
const INITIAL_USER_PROFILES = new Map(
  Array.from(userProfilesDB.entries()).map(([userId, profile]) => [
    userId,
    cloneUserProfile(profile),
  ]),
);
const INITIAL_USER_SECURITY = new Map(
  Array.from(userSecurityDB.entries()).map(([userId, security]) => [
    userId,
    cloneUserSecurity(security),
  ]),
);
const INITIAL_USER_ROLES = new Map(
  Array.from(userRolesDB.entries()).map(([userId, roles]) => [
    userId,
    roles.map(cloneUserRole),
  ]),
);
const INITIAL_USER_OVERRIDES = new Map(
  Array.from(userOverridesDB.entries()).map(([userId, overrides]) => [
    userId,
    overrides.map(cloneUserOverride),
  ]),
);

export const resetUsersMockState = () => {
  usersDB.splice(0, usersDB.length, ...INITIAL_USERS.map(cloneUser));

  userProfilesDB.clear();
  for (const [userId, profile] of INITIAL_USER_PROFILES.entries()) {
    userProfilesDB.set(userId, cloneUserProfile(profile));
  }

  userSecurityDB.clear();
  for (const [userId, security] of INITIAL_USER_SECURITY.entries()) {
    userSecurityDB.set(userId, cloneUserSecurity(security));
  }

  userRolesDB.clear();
  for (const [userId, roles] of INITIAL_USER_ROLES.entries()) {
    userRolesDB.set(userId, roles.map(cloneUserRole));
  }

  userOverridesDB.clear();
  for (const [userId, overrides] of INITIAL_USER_OVERRIDES.entries()) {
    userOverridesDB.set(userId, overrides.map(cloneUserOverride));
  }
};

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

const getRoleCatalog = () => getAvailableRoles();

const getRoleById = (roleId: number) =>
  getRoleCatalog().find((role) => role.id === roleId);

const userExists = (userId: number) =>
  usersDB.some((user) => user.id === userId);

const compareUsers = (
  firstUser: (typeof usersDB)[number],
  secondUser: (typeof usersDB)[number],
  sortBy: string,
) => {
  switch (sortBy) {
    case "username":
      return firstUser.username.localeCompare(secondUser.username);
    case "fullname":
      return firstUser.fullname.localeCompare(secondUser.fullname);
    case "email":
      return firstUser.email.localeCompare(secondUser.email);
    case "primaryRole":
      return firstUser.primaryRole.localeCompare(secondUser.primaryRole);
    case "isActive":
      return Number(firstUser.isActive) - Number(secondUser.isActive);
    default:
      return secondUser.id - firstUser.id;
  }
};

// Usamos matchers permisivos para evitar problemas con baseURL
export const usersHandlers = [
  // Listar usuarios (Paginado y Filtrado Real)
  http.get(getApiUrl("users"), async ({ request }) => {
    await delay(MOCK_DELAY.list);
    const permissionError = requirePermission("admin:gestion:usuarios:read");
    if (permissionError) return permissionError;

    const url = new URL(request.url);
    const page = Number(url.searchParams.get("page") || 1);
    const pageSize = Number(
      url.searchParams.get("pageSize") ||
        url.searchParams.get("page_size") ||
        20,
    );
    const search = url.searchParams.get("search")?.toLowerCase() || "";
    const sortBy = url.searchParams.get("sortBy") || "id";
    const sortOrder =
      (url.searchParams.get("sortOrder") || "desc").toLowerCase() === "asc"
        ? "asc"
        : "desc";
    const roleId =
      url.searchParams.get("roleId") || url.searchParams.get("rol_id");
    const clinicId =
      url.searchParams.get("clinicId") || url.searchParams.get("clinic_id");
    const estado = url.searchParams.get("estado");
    const isActiveParam = url.searchParams.get("isActive");
    const status = url.searchParams.get("status");

    // 1. Filtrado
    let filteredUsers = usersDB;

    if (search) {
      filteredUsers = filteredUsers.filter(
        (u) =>
          u.fullname.toLowerCase().includes(search) ||
          u.username.toLowerCase().includes(search) ||
          u.email.toLowerCase().includes(search),
      );
    }

    if (isActiveParam !== null) {
      const isActive = isActiveParam === "true";
      filteredUsers = filteredUsers.filter((u) => u.isActive === isActive);
    } else if (estado) {
      const isActive = estado === "A";
      filteredUsers = filteredUsers.filter((u) => u.isActive === isActive);
    }

    if (status === "pending") {
      filteredUsers = filteredUsers.filter((user) => {
        const security = userSecurityDB.get(user.id);
        const termsAccepted = security?.termsAccepted ?? user.termsAccepted;
        const mustChangePassword =
          security?.mustChangePassword ?? user.mustChangePassword;
        return !termsAccepted || mustChangePassword;
      });
    } else if (status === "active") {
      filteredUsers = filteredUsers.filter((user) => user.isActive);
    } else if (status === "inactive") {
      filteredUsers = filteredUsers.filter((user) => !user.isActive);
    }

    if (roleId) {
      const roleIdValue = Number(roleId);
      const targetRole = getRoleById(roleIdValue);
      if (targetRole) {
        filteredUsers = filteredUsers.filter(
          (u) => u.primaryRole === targetRole.name,
        );
      }
    }

    if (clinicId) {
      const clinicIdValue = Number(clinicId);
      if (Number.isFinite(clinicIdValue)) {
        filteredUsers = filteredUsers.filter(
          (u) => u.clinic?.id === clinicIdValue,
        );
      }
    }

    // 2. Paginación
    const total = filteredUsers.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const items = [...filteredUsers]
      .sort((firstUser, secondUser) => {
        const comparison = compareUsers(firstUser, secondUser, sortBy);
        return sortOrder === "asc" ? comparison : comparison * -1;
      })
      .slice(start, end)
      .map((user) => {
        const security = userSecurityDB.get(user.id);

        return {
          ...user,
          termsAccepted: security?.termsAccepted ?? user.termsAccepted ?? true,
          mustChangePassword:
            security?.mustChangePassword ?? user.mustChangePassword ?? false,
        };
      });

    return HttpResponse.json({
      items,
      page,
      pageSize,
      total,
      totalPages,
    });
  }),

  // Crear usuario (PERSISTENTE EN MEMORIA)
  http.post(getApiUrl("users"), async ({ request }) => {
    await delay(MOCK_DELAY.mutate);
    const permissionError = requirePermission("admin:gestion:usuarios:create");
    if (permissionError) return permissionError;

    const body = (await request.json()) as CreateUserRequest;

    const details: Record<string, string[]> = {};

    if (!body.username) details.username = ["Usuario requerido"];
    if (!body.firstName) details.firstName = ["Nombre requerido"];
    if (!body.paternalName)
      details.paternalName = ["Apellido paterno requerido"];
    if (!body.primaryRoleId) details.primaryRoleId = ["Selecciona un rol"];

    if (Object.keys(details).length > 0) {
      return HttpResponse.json(
        {
          code: "VALIDATION_ERROR",
          message: "Revisa los datos capturados.",
          details,
        },
        { status: 400 },
      );
    }

    // Correo opcional: solo se valida el formato cuando el usuario lo capturo.
    if (body.email && !/\S+@\S+\.\S+/.test(body.email)) {
      return HttpResponse.json(
        { code: "INVALID_EMAIL", message: "Correo invalido" },
        { status: 400 },
      );
    }

    const alreadyExists = usersDB.some(
      (user) =>
        user.username.toLowerCase() === body.username.toLowerCase() ||
        (Boolean(body.email) &&
          user.email.toLowerCase() === body.email?.toLowerCase()),
    );

    if (alreadyExists) {
      return HttpResponse.json(
        { code: "USER_EXISTS", message: "Usuario o correo ya existe" },
        { status: 409 },
      );
    }

    const primaryRole = getRoleById(body.primaryRoleId);
    if (!primaryRole) {
      return HttpResponse.json(
        { code: "ROLE_NOT_FOUND", message: "Rol no encontrado" },
        { status: 404 },
      );
    }

    if (
      body.clinicId &&
      !centrosAtencionDB.some((clinic) => clinic.id === body.clinicId)
    ) {
      return HttpResponse.json(
        { code: "CLINIC_NOT_FOUND", message: "Centro no encontrado" },
        { status: 404 },
      );
    }

    const fullname = [body.firstName, body.paternalName, body.maternalName]
      .filter(Boolean)
      .join(" ")
      .trim();

    const clinicName = body.clinicId
      ? (centrosAtencionDB.find((clinic) => clinic.id === body.clinicId)
          ?.name ?? "Centro de atencion")
      : null;

    const newUser = createMockUser({
      id: usersDB.length + 1000,
      username: body.username,
      fullname: fullname || body.username,
      email: body.email ?? "",
      clinic: body.clinicId
        ? { id: body.clinicId, name: clinicName ?? "Centro de atencion" }
        : null,
      primaryRole: primaryRole.name,
      isActive: true,
      termsAccepted: false,
      mustChangePassword: true,
    });

    // GUARDAR EN MEMORIA
    usersDB.unshift(newUser);
    userRolesDB.set(newUser.id, [buildPrimaryRole(newUser)]);
    userOverridesDB.set(newUser.id, []);
    userProfilesDB.set(newUser.id, {
      firstName: body.firstName,
      paternalName: body.paternalName,
      maternalName: body.maternalName,
    });
    userSecurityDB.set(newUser.id, {
      termsAccepted: false,
      mustChangePassword: true,
      lastLoginAt: null,
      lastIp: null,
    });

    return HttpResponse.json(
      {
        id: newUser.id,
        username: newUser.username,
      },
      { status: 201 },
    );
  }),

  // Detalle de usuario
  http.get(getApiUrl("users/:id"), async ({ params }) => {
    await delay(MOCK_DELAY.detail);
    const permissionError = requirePermission("admin:gestion:usuarios:read");
    if (permissionError) return permissionError;

    const id = Number(params.id);
    const user = usersDB.find((u) => u.id === id);

    if (!user) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    const profile =
      userProfilesDB.get(user.id) ?? buildUserProfile(user.fullname);
    const security = userSecurityDB.get(user.id) ?? {
      termsAccepted: true,
      mustChangePassword: false,
      lastLoginAt: null,
      lastIp: null,
    };
    const userDetail = createMockUserDetail({
      ...user,
      firstName: profile.firstName,
      paternalName: profile.paternalName,
      maternalName: profile.maternalName,
      termsAccepted: security.termsAccepted,
      mustChangePassword: security.mustChangePassword,
      lastLoginAt: security.lastLoginAt,
      lastIp: security.lastIp,
    });
    const roles = userRolesDB.get(user.id) ?? [buildPrimaryRole(user)];
    const overrides = userOverridesDB.get(user.id) ?? [];

    return HttpResponse.json({
      user: userDetail,
      roles,
      overrides,
    });
  }),

  // Actualizar usuario (PERSISTENTE EN MEMORIA)
  http.patch(getApiUrl("users/:id"), async ({ params, request }) => {
    await delay(MOCK_DELAY.mutate);
    const permissionError = requirePermission("admin:gestion:usuarios:update");
    if (permissionError) return permissionError;

    const id = Number(params.id);
    const body = (await request.json()) as UpdateUserRequest;

    if (body.email && !/\S+@\S+\.\S+/.test(body.email)) {
      return HttpResponse.json(
        { code: "INVALID_EMAIL", message: "Correo invalido" },
        { status: 400 },
      );
    }

    const index = usersDB.findIndex((u) => u.id === id);

    if (index === -1) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    if (
      body.email &&
      usersDB.some(
        (user) =>
          user.id !== id &&
          user.email.toLowerCase() === body.email?.toLowerCase(),
      )
    ) {
      return HttpResponse.json(
        { code: "USER_EXISTS", message: "Correo ya existe" },
        { status: 409 },
      );
    }

    if (
      body.clinicId &&
      !centrosAtencionDB.some((clinic) => clinic.id === body.clinicId)
    ) {
      return HttpResponse.json(
        { code: "CLINIC_NOT_FOUND", message: "Centro no encontrado" },
        { status: 404 },
      );
    }

    const profile =
      userProfilesDB.get(id) ?? buildUserProfile(usersDB[index].fullname);
    const nextProfile = { ...profile };

    if (body.firstName !== undefined) nextProfile.firstName = body.firstName;
    if (body.paternalName !== undefined)
      nextProfile.paternalName = body.paternalName;
    if (body.maternalName !== undefined)
      nextProfile.maternalName = body.maternalName;

    const nextFullname = [
      nextProfile.firstName,
      nextProfile.paternalName,
      nextProfile.maternalName,
    ]
      .filter(Boolean)
      .join(" ")
      .trim();

    usersDB[index] = {
      ...usersDB[index],
      ...(body.email ? { email: body.email } : {}),
      ...(body.clinicId !== undefined
        ? {
            clinic: body.clinicId
              ? {
                  id: body.clinicId,
                  name:
                    centrosAtencionDB.find(
                      (clinic) => clinic.id === body.clinicId,
                    )?.name ?? "Centro de atencion",
                }
              : null,
          }
        : {}),
      ...(nextFullname ? { fullname: nextFullname } : {}),
    };

    userProfilesDB.set(id, nextProfile);
    const updatedUser = usersDB[index];
    const security = userSecurityDB.get(id) ?? {
      termsAccepted: true,
      mustChangePassword: false,
      lastLoginAt: null,
      lastIp: null,
    };

    return HttpResponse.json({
      user: createMockUserDetail({
        ...updatedUser,
        firstName: nextProfile.firstName,
        paternalName: nextProfile.paternalName,
        maternalName: nextProfile.maternalName,
        termsAccepted: security.termsAccepted,
        mustChangePassword: security.mustChangePassword,
        lastLoginAt: security.lastLoginAt,
        lastIp: security.lastIp,
      }),
    });
  }),

  // Activar usuario (PERSISTENTE EN MEMORIA)
  http.patch(getApiUrl("users/:id/activate"), async ({ params }) => {
    await delay(MOCK_DELAY.fast);
    const permissionError = requirePermission("admin:gestion:usuarios:update");
    if (permissionError) return permissionError;

    const id = Number(params.id);

    const index = usersDB.findIndex((u) => u.id === id);
    if (index === -1) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    usersDB[index].isActive = true;

    return HttpResponse.json({ id, isActive: true });
  }),

  // Desactivar usuario (PERSISTENTE EN MEMORIA)
  http.patch(getApiUrl("users/:id/deactivate"), async ({ params }) => {
    await delay(MOCK_DELAY.fast);
    const permissionError = requirePermission("admin:gestion:usuarios:update");
    if (permissionError) return permissionError;

    const id = Number(params.id);

    const index = usersDB.findIndex((u) => u.id === id);
    if (index === -1) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    usersDB[index].isActive = false;

    return HttpResponse.json({ id, isActive: false });
  }),

  // Forzar cierre de sesion (409 si el objetivo es el usuario logueado)
  http.post(getApiUrl("users/:id/force-logout"), async ({ params }) => {
    await delay(MOCK_DELAY.fast);
    const permissionError = requirePermission("admin:gestion:usuarios:credenciales");
    if (permissionError) return permissionError;

    const id = Number(params.id);

    if (!userExists(id)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    if (id === getMockSessionUser()?.id) {
      return HttpResponse.json(
        {
          code: "SELF_FORCE_LOGOUT_NOT_ALLOWED",
          message: "No puedes forzar el cierre de tu propia sesión",
        },
        { status: 409 },
      );
    }

    return HttpResponse.json({ id, sessionRevoked: true });
  }),

  // Desbloquear login
  http.post(getApiUrl("users/:id/unlock"), async ({ params }) => {
    await delay(MOCK_DELAY.fast);
    const permissionError = requirePermission("admin:gestion:usuarios:credenciales");
    if (permissionError) return permissionError;

    const id = Number(params.id);

    if (!userExists(id)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    return HttpResponse.json({ id, unlocked: true });
  }),

  // Restablecer contraseña (con sendEmail la temporal no viaja en la respuesta)
  http.post(
    getApiUrl("users/:id/reset-password"),
    async ({ params, request }) => {
      await delay(MOCK_DELAY.fast);
      const permissionError = requirePermission(
        "admin:gestion:usuarios:credenciales",
      );
      if (permissionError) return permissionError;

      const id = Number(params.id);
      const user = usersDB.find((u) => u.id === id);

      if (!user) {
        return HttpResponse.json(
          { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
          { status: 404 },
        );
      }

      if (id === getMockSessionUser()?.id) {
        return HttpResponse.json(
          {
            code: "SELF_PASSWORD_RESET_NOT_ALLOWED",
            message: "No puedes restablecer tu propia contraseña por esta vía",
          },
          { status: 409 },
        );
      }

      const body = (await request.json().catch(() => ({}))) as {
        sendEmail?: boolean;
      };

      if (body.sendEmail) {
        if (!user.email) {
          return HttpResponse.json(
            {
              code: "USER_EMAIL_MISSING",
              message: "El usuario no tiene correo registrado",
            },
            { status: 400 },
          );
        }
        return HttpResponse.json({ emailSent: true, mustChangePassword: true });
      }

      return HttpResponse.json({
        temporaryPassword: "Temp0-Pass!",
        mustChangePassword: true,
      });
    },
  ),

  // --- GESTIÓN DE ROLES DEL USUARIO ---

  // Obtener roles (Redundante con detalle, pero por si se llama directo)
  http.get(getApiUrl("users/:id/roles"), async ({ params }) => {
    await delay(MOCK_DELAY.detail);
    const permissionError = requirePermission("admin:gestion:usuarios:read");
    if (permissionError) return permissionError;

    const userId = Number(params.id);

    if (!userExists(userId)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    const roles = userRolesDB.get(userId) ?? [];
    return HttpResponse.json({ userId, roles });
  }),

  // Asignar roles
  http.post(getApiUrl("users/:id/roles"), async ({ params, request }) => {
    await delay(MOCK_DELAY.mutate);
    const permissionError = requirePermission("admin:gestion:usuarios:update");
    if (permissionError) return permissionError;

    const userId = Number(params.id);
    const body = (await request.json()) as AssignRolesRequest;

    if (!userExists(userId)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    if (!body.roleIds || body.roleIds.length === 0) {
      return HttpResponse.json(
        { code: "VALIDATION_ERROR", message: "Selecciona al menos un rol" },
        { status: 400 },
      );
    }

    const missingRole = body.roleIds.find((roleId) => !getRoleById(roleId));

    if (missingRole) {
      return HttpResponse.json(
        { code: "ROLE_NOT_FOUND", message: "Rol no encontrado" },
        { status: 404 },
      );
    }

    const existingRoles = userRolesDB.get(userId) ?? [];
    const newRoles = (body.roleIds || [])
      .map((roleId: number) => {
        const roleMatch = getRoleById(roleId);
        return createMockUserRole({
          id: roleId,
          name: roleMatch?.name ?? `Rol ${roleId}`,
          isPrimary: false,
        });
      })
      .filter(
        (role) => !existingRoles.some((existing) => existing.id === role.id),
      );

    const updatedRoles = [...existingRoles, ...newRoles];
    if (updatedRoles.length > 0 && !updatedRoles.some((r) => r.isPrimary)) {
      updatedRoles[0].isPrimary = true;
    }
    userRolesDB.set(userId, updatedRoles);

    const userIndex = usersDB.findIndex((user) => user.id === userId);
    const primaryRole = updatedRoles.find((role) => role.isPrimary);
    if (userIndex !== -1 && primaryRole) {
      usersDB[userIndex].primaryRole = primaryRole.name;
    }

    return HttpResponse.json(
      {
        userId,
        roles: updatedRoles,
      },
      { status: 201 },
    );
  }),

  // Cambiar rol primario
  http.put(
    getApiUrl("users/:id/roles/primary"),
    async ({ params, request }) => {
      await delay(MOCK_DELAY.fast);
      const permissionError = requirePermission(
        "admin:gestion:usuarios:update",
      );
      if (permissionError) return permissionError;

      const userId = Number(params.id);
      const body = (await request.json()) as SetPrimaryRoleRequest;

      if (!userExists(userId)) {
        return HttpResponse.json(
          { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
          { status: 404 },
        );
      }

      const roles = userRolesDB.get(userId) ?? [];

      if (!roles.some((role) => role.id === body.roleId)) {
        return HttpResponse.json(
          { code: "ROLE_NOT_FOUND", message: "Rol no encontrado" },
          { status: 404 },
        );
      }
      const updatedRoles = roles.map((role) => ({
        ...role,
        isPrimary: role.id === body.roleId,
      }));
      userRolesDB.set(userId, updatedRoles);

      const userIndex = usersDB.findIndex((user) => user.id === userId);
      const primaryRole = updatedRoles.find((role) => role.isPrimary);
      if (userIndex !== -1 && primaryRole) {
        usersDB[userIndex].primaryRole = primaryRole.name;
      }
      return HttpResponse.json({ userId, roles: updatedRoles });
    },
  ),

  // Revocar rol
  http.delete(getApiUrl("users/:id/roles/:roleId"), async ({ params }) => {
    await delay(MOCK_DELAY.fast);
    const permissionError = requirePermission("admin:gestion:usuarios:update");
    if (permissionError) return permissionError;

    const userId = Number(params.id);
    const roleId = Number(params.roleId);

    if (!userExists(userId)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    const roles = userRolesDB.get(userId) ?? [];

    if (!roles.some((role) => role.id === roleId)) {
      return HttpResponse.json(
        { code: "ROLE_NOT_FOUND", message: "Rol no encontrado" },
        { status: 404 },
      );
    }

    if (roles.length <= 1) {
      return HttpResponse.json(
        {
          code: "CANNOT_REMOVE_LAST_ROLE",
          message: "El usuario debe conservar al menos un rol",
        },
        { status: 400 },
      );
    }

    const updatedRoles = roles.filter((role) => role.id !== roleId);
    if (!updatedRoles.some((role) => role.isPrimary) && updatedRoles[0]) {
      updatedRoles[0].isPrimary = true;
    }
    userRolesDB.set(userId, updatedRoles);

    const userIndex = usersDB.findIndex((user) => user.id === userId);
    const primaryRole = updatedRoles.find((role) => role.isPrimary);
    if (userIndex !== -1 && primaryRole) {
      usersDB[userIndex].primaryRole = primaryRole.name;
    }

    return HttpResponse.json({ userId, roles: updatedRoles });
  }),

  // --- GESTION DE OVERRIDES ---

  http.get(getApiUrl("users/:id/overrides"), async ({ params }) => {
    await delay(MOCK_DELAY.detail);
    const permissionError = requirePermission("admin:gestion:usuarios:read");
    if (permissionError) return permissionError;

    const userId = Number(params.id);

    if (!userExists(userId)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    const overrides = userOverridesDB.get(userId) ?? [];
    return HttpResponse.json({
      userId,
      overrides,
    });
  }),

  http.post(getApiUrl("users/:id/overrides"), async ({ params, request }) => {
    await delay(MOCK_DELAY.mutate);
    const permissionError = requirePermission("admin:gestion:usuarios:update");
    if (permissionError) return permissionError;

    const userId = Number(params.id);
    const body = (await request.json()) as AddUserOverrideRequest;

    if (!userExists(userId)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    const overrides = userOverridesDB.get(userId) ?? [];
    const permissionMeta = permissionsCatalog.find(
      (permission) => permission.code === body.permissionCode,
    );

    if (
      !permissionsCatalog.some(
        (permission) => permission.code === body.permissionCode,
      )
    ) {
      return HttpResponse.json(
        { code: "PERMISSION_NOT_FOUND", message: "Permiso no encontrado" },
        { status: 404 },
      );
    }

    if (body.effect !== "ALLOW" && body.effect !== "DENY") {
      return HttpResponse.json(
        { code: "VALIDATION_ERROR", message: "Efecto invalido" },
        { status: 400 },
      );
    }
    const existingIndex = overrides.findIndex(
      (override) => override.permissionCode === body.permissionCode,
    );
    const nextOverride = createMockUserOverride({
      permissionCode: body.permissionCode,
      permissionDescription: permissionMeta?.description ?? "Permiso",
      effect: body.effect,
      expiresAt: body.expiresAt ?? null,
    });

    let updatedOverrides = overrides;
    if (existingIndex >= 0) {
      updatedOverrides = overrides.map((override, index) =>
        index === existingIndex ? { ...override, ...nextOverride } : override,
      );
    } else {
      updatedOverrides = [...overrides, nextOverride];
    }
    userOverridesDB.set(userId, updatedOverrides);

    return HttpResponse.json({
      userId,
      overrides: updatedOverrides,
    });
  }),

  http.delete(getApiUrl("users/:id/overrides/:code"), async ({ params }) => {
    await delay(MOCK_DELAY.fast);
    const permissionError = requirePermission("admin:gestion:usuarios:update");
    if (permissionError) return permissionError;

    const userId = Number(params.id);
    const code = String(params.code);

    if (!userExists(userId)) {
      return HttpResponse.json(
        { code: "USER_NOT_FOUND", message: "Usuario no encontrado" },
        { status: 404 },
      );
    }

    const overrides = userOverridesDB.get(userId) ?? [];

    if (!overrides.some((override) => override.permissionCode === code)) {
      return HttpResponse.json(
        { code: "PERMISSION_NOT_FOUND", message: "Permiso no encontrado" },
        { status: 404 },
      );
    }
    const updatedOverrides = overrides.filter(
      (override) => override.permissionCode !== code,
    );
    userOverridesDB.set(userId, updatedOverrides);

    return HttpResponse.json({
      userId,
      overrides: updatedOverrides,
    });
  }),
];
