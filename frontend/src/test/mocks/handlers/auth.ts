import { http, HttpResponse, delay } from "msw";
import type { AuthUser } from "@api/types/auth.types";
import { createMockAuthUser } from "../../factories/users";
import { getApiUrl } from "../urls";
import {
  clearMockSessionUser,
  getMockSessionUser,
  resetMockSessionUser,
  setMockSessionUser,
} from "../session";
import { resetRolesMockState } from "./roles";
import { resetUsersMockState } from "./users";
import { getScenarioCredentials } from "@/test/e2e/auth/auth-dataset";

interface LoginScenario {
  user: AuthUser;
  requiresOnboarding?: boolean;
}

const INACTIVE_SCENARIO_USERNAMES = new Set([
  getScenarioCredentials("backend-real", "inactive_user").username,
  getScenarioCredentials("hybrid", "inactive_user").username,
]);

const BLOCKED_SCENARIO_USERNAMES = new Set([
  getScenarioCredentials("backend-real", "blocked_user").username,
  getScenarioCredentials("hybrid", "blocked_user").username,
]);

const ONBOARDING_SCENARIO_USERNAMES = new Set([
  getScenarioCredentials("backend-real", "onboarding_user").username,
  getScenarioCredentials("hybrid", "onboarding_user").username,
]);

const PASSWORD_RESET_SCENARIO_USERNAMES = new Set([
  getScenarioCredentials("backend-real", "password_reset_user").username,
  getScenarioCredentials("hybrid", "password_reset_user").username,
]);

const MOCK_DELAY = {
  auth: 900,
  short: 600,
  long: 1200,
};

const testUserOverrides = new Map<
  string,
  { requiresOnboarding?: boolean; mustChangePassword?: boolean }
>();

const resetCodeStore = new Map<string, string>();

const ACCESS_TOKEN_COOKIE = "access_token_cookie";
const REFRESH_TOKEN_COOKIE = "refresh_token_cookie";
const CSRF_COOKIE = "csrf_token";
const COOKIE_PATH = "Path=/";
const COOKIE_SAME_SITE = "SameSite=Lax";

// Función helper para validar contraseñas robustas (replica lógica de Zod del frontend)
const isPasswordStrong = (password: string): boolean => {
  const hasMinLength = password.length >= 8;
  const hasUpperCase = /[A-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecialChar = /[^a-zA-Z0-9]/.test(password);

  return hasMinLength && hasUpperCase && hasNumber && hasSpecialChar;
};

// Helper para crear respuesta de login consistente
const createLoginResponse = (user: AuthUser, requiresOnboarding = false) => {
  const tokenValue = encodeURIComponent(user.username);
  const csrfToken = `csrf_${tokenValue}`;

  const headers = new Headers();
  headers.append(
    "Set-Cookie",
    `${ACCESS_TOKEN_COOKIE}=${tokenValue}; ${COOKIE_PATH}; HttpOnly; ${COOKIE_SAME_SITE}`,
  );
  headers.append(
    "Set-Cookie",
    `${REFRESH_TOKEN_COOKIE}=${tokenValue}; ${COOKIE_PATH}; HttpOnly; ${COOKIE_SAME_SITE}`,
  );
  headers.append(
    "Set-Cookie",
    `${CSRF_COOKIE}=${csrfToken}; ${COOKIE_PATH}; ${COOKIE_SAME_SITE}`,
  );

  return HttpResponse.json(
    {
      user,
      requiresOnboarding,
    },
    {
      headers,
    },
  );
};

const createLogoutHeaders = () => {
  const headers = new Headers();

  headers.append(
    "Set-Cookie",
    `${ACCESS_TOKEN_COOKIE}=; ${COOKIE_PATH}; Max-Age=0; ${COOKIE_SAME_SITE}`,
  );
  headers.append(
    "Set-Cookie",
    `${REFRESH_TOKEN_COOKIE}=; ${COOKIE_PATH}; Max-Age=0; ${COOKIE_SAME_SITE}`,
  );
  headers.append(
    "Set-Cookie",
    `${CSRF_COOKIE}=; ${COOKIE_PATH}; Max-Age=0; ${COOKIE_SAME_SITE}`,
  );

  return headers;
};

const createRefreshHeaders = (username: string) => {
  const headers = new Headers();
  headers.append(
    "Set-Cookie",
    `${CSRF_COOKIE}=csrf_${encodeURIComponent(username)}; ${COOKIE_PATH}; ${COOKIE_SAME_SITE}`,
  );
  return headers;
};

const createAuthRevisionHeaders = (authRevision: string) => {
  const headers = new Headers();
  headers.set("X-Auth-Revision", authRevision);
  return headers;
};

const createContractErrorResponse = (
  status: number,
  code: string,
  message: string,
  requestId = `req-${code.toLowerCase()}`,
) => {
  const headers = new Headers();
  headers.set("X-Request-ID", requestId);

  return HttpResponse.json(
    {
      code,
      message,
      status,
      requestId,
    },
    { status, headers },
  );
};

const loginSuccessResponse = (user: AuthUser, requiresOnboarding = false) => {
  setMockSessionUser(user);
  return createLoginResponse(user, requiresOnboarding);
};

const getCookieValue = (cookieHeader: string, key: string) => {
  const pair = cookieHeader
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${key}=`));

  if (!pair) return null;
  return pair.slice(key.length + 1);
};

const buildLoginScenario = (username: string): LoginScenario => {
  if (username === "admin") {
    return {
      user: createMockAuthUser({
        username: "admin",
        fullName: "Administrador",
        landingRoute: "/admin/roles",
        roles: ["Admin"],
        avatarUrl: "https://i.pravatar.cc/96?img=8",
        permissions: ["*"],
      }),
    };
  }

  if (username === "admin_usuarios_readonly") {
    return {
      user: createMockAuthUser({
        username: "admin_usuarios_readonly",
        fullName: "Admin Usuarios Lectura",
        landingRoute: "/admin/usuarios",
        roles: ["Admin Usuarios"],
        avatarUrl: "https://i.pravatar.cc/96?img=9",
        permissions: [
          "admin:gestion:usuarios:read",
          "admin:gestion:roles:read",
        ],
      }),
    };
  }

  if (username === "admin_roles_readonly") {
    return {
      user: createMockAuthUser({
        username: "admin_roles_readonly",
        fullName: "Admin Roles Lectura",
        landingRoute: "/admin/roles",
        roles: ["Admin Roles"],
        avatarUrl: "https://i.pravatar.cc/96?img=10",
        permissions: ["admin:gestion:roles:read"],
      }),
    };
  }

  if (username === "admin_roles_manager") {
    return {
      user: createMockAuthUser({
        username: "admin_roles_manager",
        fullName: "Admin Gestor Roles",
        landingRoute: "/admin/roles",
        roles: ["Admin Roles"],
        avatarUrl: "https://i.pravatar.cc/96?img=11",
        permissions: [
          "admin:gestion:roles:read",
          "admin:gestion:roles:create",
          "admin:gestion:roles:update",
          "admin:gestion:roles:delete",
          "admin:gestion:permisos:read",
        ],
      }),
    };
  }

  if (username === "clinico" || username === "medico") {
    return {
      user: createMockAuthUser({
        username: "clinico",
        fullName: "Dra. Rivera",
        landingRoute: "/clinico/consultas",
        roles: ["Clinico"],
        avatarUrl: "https://i.pravatar.cc/96?img=15",
        permissions: [
          "clinico:consultas:read",
          "clinico:consultas:create",
          "clinico:expedientes:read",
          "clinico:somatometria:read",
          "admin:catalogos:centros_atencion:read",
        ],
        capabilities: {
          "flow.somatometria.queue.read": {
            granted: true,
            missingAllOf: [],
            missingAnyOf: [],
          },
          "flow.somatometria.capture": {
            granted: true,
            missingAllOf: [],
            missingAnyOf: [],
          },
          "flow.doctor.queue.read": {
            granted: true,
            missingAllOf: [],
            missingAnyOf: [],
          },
          "flow.doctor.consultation.start": {
            granted: true,
            missingAllOf: [],
            missingAnyOf: [],
          },
          "flow.doctor.consultation.close": {
            granted: true,
            missingAllOf: [],
            missingAnyOf: [],
          },
        },
      }),
    };
  }

  if (username === "recepcion") {
    return {
      user: createMockAuthUser({
        username: "recepcion",
        fullName: "Recepcion Central",
        landingRoute: "/recepcion/agenda",
        roles: ["Recepcion"],
        avatarUrl: "https://i.pravatar.cc/96?img=21",
        permissions: [
          "recepcion:fichas:medicina_general:create",
          "recepcion:fichas:especialidad:create",
          "recepcion:fichas:urgencias:create",
          "recepcion:incapacidad:read",
          "clinico:consultas:read",
          "clinico:somatometria:read",
          "clinico:expedientes:read",
        ],
        capabilities: {
          "flow.visits.queue.read": {
            granted: true,
            missingAllOf: [],
            missingAnyOf: [],
          },
          "flow.recepcion.queue.write": {
            granted: true,
            missingAllOf: [],
            missingAnyOf: [],
          },
        },
      }),
    };
  }

  if (username === "farmacia") {
    return {
      user: createMockAuthUser({
        username: "farmacia",
        fullName: "Farmacia Principal",
        landingRoute: "/farmacia/recetas",
        roles: ["Farmacia"],
        avatarUrl: "https://i.pravatar.cc/96?img=31",
        permissions: [
          "farmacia:recetas:dispensar",
          "farmacia:inventario:update",
        ],
      }),
    };
  }

  if (username === "urgencias") {
    return {
      user: createMockAuthUser({
        username: "urgencias",
        fullName: "Medico Urgencias",
        landingRoute: "/urgencias/triage",
        roles: ["Urgencias"],
        avatarUrl: "https://i.pravatar.cc/96?img=45",
        permissions: ["urgencias:triage:read"],
      }),
    };
  }

  if (username === "hospital") {
    return {
      user: createMockAuthUser({
        username: "hospital",
        fullName: "Coord. Hospitalaria",
        roles: ["HOSPITAL"],
        permissions: [
          "hospital:coordinacion",
          "hospital:admision",
          "hospital:camas",
        ],
      }),
    };
  }

  if (ONBOARDING_SCENARIO_USERNAMES.has(username)) {
    return {
      user: createMockAuthUser({
        username,
        mustChangePassword: true,
        requiresOnboarding: true,
      }),
      requiresOnboarding: true,
    };
  }

  if (PASSWORD_RESET_SCENARIO_USERNAMES.has(username)) {
    return {
      user: createMockAuthUser({
        username,
        mustChangePassword: true,
      }),
      requiresOnboarding: false,
    };
  }

  return {
    user: createMockAuthUser({ username }),
  };
};

const applyTestUserOverride = (
  username: string,
  scenario: LoginScenario,
): LoginScenario => {
  const override = testUserOverrides.get(username);
  if (!override) return scenario;

  return {
    user: {
      ...scenario.user,
      ...(override.mustChangePassword !== undefined
        ? { mustChangePassword: override.mustChangePassword }
        : {}),
      ...(override.requiresOnboarding !== undefined
        ? { requiresOnboarding: override.requiresOnboarding }
        : {}),
    },
    requiresOnboarding:
      override.requiresOnboarding ?? scenario.requiresOnboarding,
  };
};

const resolveSessionUser = (
  request: Request,
  cookies?: Record<string, string>,
) => {
  const currentSessionUser = getMockSessionUser();
  if (currentSessionUser) return currentSessionUser;

  const accessTokenFromStore = cookies?.access_token_cookie;
  const cookieHeader = request.headers.get("cookie") ?? "";
  const accessToken =
    accessTokenFromStore ?? getCookieValue(cookieHeader, "access_token_cookie");

  if (!accessToken) return null;

  const username = decodeURIComponent(accessToken);
  const { user } = applyTestUserOverride(
    username,
    buildLoginScenario(username),
  );
  setMockSessionUser(user);
  return user;
};

export const authHandlers = [
  // ============================================================
  // SESIÓN Y LOGIN
  // ============================================================

  http.post(getApiUrl("auth/login"), async ({ request }) => {
    await delay(MOCK_DELAY.auth);

    const body = (await request.json()) as {
      username: string;
      password: string;
    };
    const { username, password } = body;

    // --- ESCENARIOS DE ERROR "MÁGICOS" ---

    // 1. Credenciales Inválidas
    if (username === "error" || password === "wrong") {
      return createContractErrorResponse(
        401,
        "INVALID_CREDENTIALS",
        "Usuario o contraseña incorrectos",
      );
    }

    // 2. Usuario Bloqueado
    if (BLOCKED_SCENARIO_USERNAMES.has(username)) {
      return createContractErrorResponse(
        423,
        "ACCOUNT_LOCKED",
        "Tu cuenta ha sido bloqueada temporalmente por múltiples intentos fallidos. Intenta en 15 minutos.",
      );
    }

    // 3. Usuario Inactivo
    if (INACTIVE_SCENARIO_USERNAMES.has(username)) {
      return createContractErrorResponse(
        403,
        "USER_INACTIVE",
        "Tu cuenta ha sido desactivada por un administrador.",
      );
    }

    // 4. Cuenta Expirada (Nuevo)
    if (username === "expired") {
      return createContractErrorResponse(
        401,
        "ACCOUNT_EXPIRED",
        "Tu cuenta ha expirado. Contacta a soporte.",
      );
    }

    // 5. Mantenimiento (Nuevo)
    if (username === "maintenance") {
      return createContractErrorResponse(
        503,
        "SERVICE_UNAVAILABLE",
        "El sistema está en mantenimiento. Vuelve en unos minutos.",
      );
    }

    // 6. Error Interno
    if (username === "broken") {
      return createContractErrorResponse(
        500,
        "INTERNAL_SERVER_ERROR",
        "Error interno del servidor. Intente más tarde.",
      );
    }

    const scenario = applyTestUserOverride(
      username,
      buildLoginScenario(username),
    );
    return loginSuccessResponse(
      scenario.user,
      scenario.requiresOnboarding ?? false,
    );
  }),

  http.post(getApiUrl("auth/logout"), async () => {
    await delay(MOCK_DELAY.short);
    clearMockSessionUser();

    return HttpResponse.json(
      {
        success: true,
        message: "Sesion cerrada correctamente",
      },
      {
        headers: createLogoutHeaders(),
      },
    );
  }),

  http.get(getApiUrl("auth/me"), async ({ request, cookies }) => {
    await delay(MOCK_DELAY.short);
    const user = resolveSessionUser(request, cookies);

    if (!user) {
      return createContractErrorResponse(
        401,
        "SESSION_EXPIRED",
        "La sesion no es valida o ha expirado.",
      );
    }

    return HttpResponse.json(user, {
      headers: createAuthRevisionHeaders(user.authRevision),
    });
  }),

  http.get(getApiUrl("auth/capabilities"), async ({ request, cookies }) => {
    await delay(MOCK_DELAY.short);
    const user = resolveSessionUser(request, cookies);

    if (!user) {
      return createContractErrorResponse(
        401,
        "SESSION_EXPIRED",
        "La sesion no es valida o ha expirado.",
      );
    }

    return HttpResponse.json(
      {
        permissions: user.permissions,
        effectivePermissions: user.effectivePermissions,
        capabilities: user.capabilities,
        permissionDependenciesVersion: user.permissionDependenciesVersion,
        strictCapabilityPrefixes: user.strictCapabilityPrefixes,
        authRevision: user.authRevision,
      },
      {
        headers: createAuthRevisionHeaders(user.authRevision),
      },
    );
  }),

  http.post(getApiUrl("auth/refresh"), async ({ request, cookies }) => {
    await delay(MOCK_DELAY.short);
    const user = resolveSessionUser(request, cookies);

    if (!user) {
      return createContractErrorResponse(
        401,
        "REFRESH_TOKEN_EXPIRED",
        "No hay refresh token valido.",
      );
    }

    return HttpResponse.json(
      { success: true, message: "Sesion renovada" },
      {
        headers: createRefreshHeaders(user.username),
      },
    );
  }),

  http.get(getApiUrl("auth/verify"), async ({ request, cookies }) => {
    const user = resolveSessionUser(request, cookies);

    if (!user) {
      return createContractErrorResponse(
        401,
        "SESSION_EXPIRED",
        "La sesion no es valida o ha expirado.",
      );
    }

    return HttpResponse.json({ valid: true });
  }),

  // ============================================================
  // RECUPERACIÓN DE CONTRASEÑA
  // ============================================================

  http.post(getApiUrl("auth/request-reset-code"), async ({ request }) => {
    await delay(MOCK_DELAY.long);
    const body = (await request.json()) as { email: string };

    if (
      body.email === "error@fail.com" ||
      body.email.toLowerCase().includes("noexiste")
    ) {
      return createContractErrorResponse(
        404,
        "USER_NOT_FOUND",
        "No encontramos un usuario con ese correo.",
      );
    }

    resetCodeStore.set(body.email.toLowerCase(), "123456");

    return HttpResponse.json({
      success: true,
      message: "Si el correo existe, se ha enviado un codigo de verificacion.",
    });
  }),

  http.post(getApiUrl("auth/verify-reset-code"), async ({ request }) => {
    await delay(MOCK_DELAY.long);
    const body = (await request.json()) as {
      email: string;
      code: string | number;
    };

    // Convertir a string para asegurar comparación correcta
    const code = String(body.code);
    const expectedCode =
      resetCodeStore.get(body.email.toLowerCase()) ?? "123456";

    if (code === expectedCode) {
      return HttpResponse.json({
        valid: true,
      });
    }

    if (code === "000000") {
      return createContractErrorResponse(
        400,
        "CODE_EXPIRED",
        "El código ha expirado. Solicita uno nuevo.",
      );
    }

    // Nuevo: Exceso de intentos
    if (code === "999999") {
      return createContractErrorResponse(
        400,
        "CODE_EXPIRED",
        "Código invalidado por demasiados intentos.",
      );
    }

    return createContractErrorResponse(
      400,
      "INVALID_CODE",
      "Código incorrecto. Verifica los 6 dígitos.",
    );
  }),

  http.post(getApiUrl("auth/reset-password"), async ({ request }) => {
    await delay(MOCK_DELAY.long);
    const body = (await request.json()) as { newPassword: string };

    if (!body.newPassword || body.newPassword.trim().length === 0) {
      return createContractErrorResponse(
        400,
        "VALIDATION_ERROR",
        "Hay errores en el formulario",
      );
    }

    // Simulación de Token Expirado
    if (body.newPassword === "ExpiredToken1!") {
      return createContractErrorResponse(
        401,
        "TOKEN_EXPIRED",
        "Tu sesión ha expirado. Solicita un nuevo código.",
      );
    }

    // Simulación de Token Inválido
    if (body.newPassword === "TokenInvalid1!") {
      return createContractErrorResponse(
        401,
        "TOKEN_INVALID",
        "El token de restablecimiento es inválido o ha expirado.",
      );
    }

    // Simulación de Error Interno
    if (body.newPassword === "InvalidToken1!") {
      return createContractErrorResponse(
        500,
        "INTERNAL_SERVER_ERROR",
        "No se pudo restablecer la contraseña. Intente nuevamente.",
      );
    }

    // Validación Robusta de Contraseña
    if (!isPasswordStrong(body.newPassword)) {
      return createContractErrorResponse(
        400,
        "PASSWORD_TOO_WEAK",
        "La contraseña es demasiado débil",
      );
    }

    const user = createMockAuthUser();
    setMockSessionUser(user);

    return createLoginResponse(user, false);
  }),

  http.post(getApiUrl("auth/change-password"), async ({ request }) => {
    await delay(MOCK_DELAY.short);
    const body = (await request.json()) as {
      currentPassword: string;
      newPassword: string;
    };

    if (body.currentPassword !== "password123") {
      return createContractErrorResponse(
        401,
        "INVALID_CREDENTIALS",
        "Usuario o contraseña incorrectos",
      );
    }

    if (!body.newPassword || body.newPassword.trim().length === 0) {
      return createContractErrorResponse(
        400,
        "VALIDATION_ERROR",
        "Hay errores en el formulario",
      );
    }

    if (body.currentPassword === body.newPassword) {
      return createContractErrorResponse(
        400,
        "VALIDATION_ERROR",
        "Hay errores en el formulario",
      );
    }

    if (!isPasswordStrong(body.newPassword)) {
      return createContractErrorResponse(
        400,
        "PASSWORD_TOO_WEAK",
        "La contraseña es demasiado débil",
      );
    }

    return HttpResponse.json({ success: true });
  }),

  // ============================================================
  // ONBOARDING
  // ============================================================

  http.post(getApiUrl("auth/complete-onboarding"), async ({ request }) => {
    await delay(MOCK_DELAY.long);
    const body = (await request.json()) as {
      newPassword: string;
      termsAccepted: boolean;
    };

    // Validar Términos
    if (body.termsAccepted === false) {
      return createContractErrorResponse(
        400,
        "TERMS_NOT_ACCEPTED",
        "Debes aceptar los términos y condiciones.",
      );
    }

    if (!body.newPassword || body.newPassword.trim().length === 0) {
      return createContractErrorResponse(
        400,
        "VALIDATION_ERROR",
        "Hay errores en el formulario",
      );
    }

    // Simulación de Token Expirado (Onboarding)
    if (body.newPassword === "ExpiredToken1!") {
      return createContractErrorResponse(
        401,
        "TOKEN_EXPIRED",
        "Tu sesión ha expirado. Inicia sesión nuevamente.",
      );
    }

    // Simulación de Fallo Genérico en Onboarding
    // Usamos la password mágica "InvalidToken1!" para simular que algo falló en el backend
    if (body.newPassword === "InvalidToken1!") {
      return createContractErrorResponse(
        500,
        "ONBOARDING_FAILED",
        "No se pudo completar el registro. Intente nuevamente.",
      );
    }

    // Validación Robusta de Contraseña
    if (!isPasswordStrong(body.newPassword)) {
      return createContractErrorResponse(
        400,
        "PASSWORD_TOO_WEAK",
        "La contraseña es demasiado débil",
      );
    }

    const user = createMockAuthUser({
      mustChangePassword: false,
    });
    setMockSessionUser(user);

    return createLoginResponse(user, false);
  }),

  // ============================================================
  // TEST HELPERS
  // ============================================================

  http.post(getApiUrl("auth/test-reset-state"), async () => {
    resetRolesMockState();
    resetUsersMockState();
    resetMockSessionUser();
    testUserOverrides.clear();
    resetCodeStore.clear();

    return HttpResponse.json({ success: true });
  }),

  http.post(getApiUrl("auth/test-reset-user"), async ({ request }) => {
    const body = (await request.json()) as {
      username: string;
      requiresOnboarding?: boolean;
      mustChangePassword?: boolean;
    };

    testUserOverrides.set(body.username, {
      requiresOnboarding: body.requiresOnboarding,
      mustChangePassword: body.mustChangePassword,
    });

    return HttpResponse.json({ success: true });
  }),

  http.get(getApiUrl("auth/test-get-otp"), async ({ request }) => {
    const url = new URL(request.url);
    const email = url.searchParams.get("email")?.toLowerCase() ?? "";
    const code = resetCodeStore.get(email) ?? "123456";

    return HttpResponse.json({ code });
  }),
];
