import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import type { UseMutationOptions, DefaultError } from "@tanstack/react-query";
import type {
  AuthUser,
  LoginRequest,
  LoginResponse,
  LogoutResponse,
  RefreshTokenResponse,
} from "@api/types";
import { createMockAuthUser } from "@/test/factories/users";

const navigateMock = vi.fn();
const useMutationMock = vi.fn(
  (options: UseMutationOptions<unknown, DefaultError, unknown, unknown>) =>
    options,
);
const useQueryClientMock = vi.fn<() => QueryClient>();
const invalidateAuthSessionAndCapabilitiesMock = vi.fn();
const setAuthSessionMock = vi.fn();
const clearAuthSessionMock = vi.fn();

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>(
    "@tanstack/react-query",
  );

  return {
    ...actual,
    useMutation: <TData, TVariables>(
      options: UseMutationOptions<TData, DefaultError, TVariables, unknown>,
    ) =>
      useMutationMock(
        options as UseMutationOptions<unknown, DefaultError, unknown, unknown>,
      ) as UseMutationOptions<TData, DefaultError, TVariables, unknown>,
    useQueryClient: () => useQueryClientMock(),
  };
});

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useLocation: () => ({ pathname: "/login", state: null }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
    promise: vi.fn(),
  },
}));

vi.mock("@api/resources/auth.api", () => ({
  authAPI: {
    login: vi.fn(),
    logout: vi.fn(),
    refreshToken: vi.fn(),
  },
}));

vi.mock("@/domains/auth-access/adapters/auth-query-invalidation", () => ({
  invalidateAuthSessionAndCapabilities: (queryClient: QueryClient) =>
    invalidateAuthSessionAndCapabilitiesMock(queryClient),
}));

vi.mock("@/domains/auth-access/adapters/auth-cache", () => ({
  setAuthSession: (queryClient: QueryClient, user: AuthUser) =>
    setAuthSessionMock(queryClient, user),
  clearAuthSession: (queryClient: QueryClient) =>
    clearAuthSessionMock(queryClient),
}));

vi.mock("@app/state/ui/sidebarStore", () => ({
  useSidebarStore: {
    getState: () => ({
      resetSidebarState: vi.fn(),
    }),
  },
}));

vi.mock("@app/state/ui/themeStore", () => ({
  useThemeStore: {
    getState: () => ({
      resetTheme: vi.fn(),
    }),
  },
}));

import { useLogin } from "@/domains/auth-access/hooks/useLogin";
import { useLogout } from "@/domains/auth-access/hooks/useLogout";
import { useRefreshSession } from "@/domains/auth-access/hooks/useRefreshSession";

type LoginMutationVariables = LoginRequest & { rememberMe: boolean };

type MutationLike<TData, TVariables> = {
  onSuccess?: (
    data: TData,
    variables: TVariables,
    context?: unknown,
    mutation?: unknown,
  ) => void;
};

const createQueryClientDouble = (): QueryClient => {
  return new QueryClient();
};

const asMutationLike = <TData, TVariables>(
  value: unknown,
): MutationLike<TData, TVariables> => value as MutationLike<TData, TVariables>;

describe("auth mutations sync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useQueryClientMock.mockReturnValue(createQueryClientDouble());
  });

  it("invalidates session+capabilities after successful login", () => {
    const queryClient = createQueryClientDouble();
    useQueryClientMock.mockReturnValue(queryClient);

    const mutation = asMutationLike<LoginResponse, LoginMutationVariables>(
      useLogin(),
    );

    const loginResponse: LoginResponse = {
      user: createMockAuthUser({
        fullName: "Admin User",
        landingRoute: "/admin",
      }),
      requiresOnboarding: false,
    };

    mutation.onSuccess?.(loginResponse, {
      username: "admin",
      password: "secret",
      rememberMe: false,
    });

    expect(setAuthSessionMock).toHaveBeenCalledWith(
      queryClient,
      expect.objectContaining({ fullName: "Admin User" }),
    );
    expect(invalidateAuthSessionAndCapabilitiesMock).toHaveBeenCalledWith(
      queryClient,
    );
  });

  it("invalidates session+capabilities after successful refresh", () => {
    const queryClient = createQueryClientDouble();
    useQueryClientMock.mockReturnValue(queryClient);

    const mutation = asMutationLike<RefreshTokenResponse, void>(
      useRefreshSession(),
    );

    mutation.onSuccess?.({ success: true }, undefined, undefined, undefined);

    expect(invalidateAuthSessionAndCapabilitiesMock).toHaveBeenCalledWith(
      queryClient,
    );
  });

  it("clears auth caches on logout success", () => {
    const queryClient = createQueryClientDouble();
    useQueryClientMock.mockReturnValue(queryClient);

    const mutation = asMutationLike<LogoutResponse, void>(useLogout());
    mutation.onSuccess?.({ success: true }, undefined, undefined, undefined);

    expect(clearAuthSessionMock).toHaveBeenCalledWith(queryClient);
  });
});
