import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent, {
  PointerEventsCheckLevel,
} from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import UsersPage from "@/domains/auth-access/pages/admin/users/UsersPage";
import { createMockUser } from "@/test/factories/users";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useAuthCapabilities } from "@/domains/auth-access/hooks/useAuthCapabilities";
import { useUsersList } from "@/domains/auth-access/hooks/rbac/users/useUsersList";
import { useRolesList } from "@/domains/auth-access/hooks/rbac/roles/useRolesList";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useAuthSession } from "@/domains/auth-access/hooks/useAuthSession";
import type { CentroAtencionListItem, RoleListItem } from "@api/types";
import { ApiError } from "@api/utils/errors";

const userDetailsDialogPropsSpy = vi.fn();

vi.mock("@shared/hooks/useDebounce", () => ({
  useDebounce: (value: string) => value,
}));

vi.mock(
  "@/domains/auth-access/components/admin/rbac/users/UserDetailsDialog",
  () => ({
    UserDetailsDialog: ({
      open,
      canEdit,
      canManageCredentials,
      canReadRolesCatalog,
      canReadPermissionsCatalog,
    }: {
      open: boolean;
      canEdit?: boolean;
      canManageCredentials?: boolean;
      canReadRolesCatalog?: boolean;
      canReadPermissionsCatalog?: boolean;
    }) => {
      userDetailsDialogPropsSpy({
        open,
        canEdit,
        canManageCredentials,
        canReadRolesCatalog,
        canReadPermissionsCatalog,
      });
      return open ? <div>Detalles abiertos</div> : null;
    },
  }),
);

vi.mock(
  "@/domains/auth-access/components/admin/rbac/users/UserCreateDialog",
  () => ({
    UserCreateDialog: ({ open }: { open: boolean }) =>
      open ? <div>Crear abierto</div> : null,
  }),
);

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/useAuthCapabilities", () => ({
  useAuthCapabilities: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useUsersList", () => ({
  useUsersList: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/rbac/roles/useRolesList", () => ({
  useRolesList: vi.fn(),
}));

vi.mock(
  "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList",
  () => ({
    useCentrosAtencionList: vi.fn(),
  }),
);

vi.mock("@/domains/auth-access/hooks/useAuthSession", () => ({
  useAuthSession: vi.fn(),
}));

const createRoleOption = (
  overrides: Partial<RoleListItem> = {},
): RoleListItem => ({
  id: 1,
  name: "Admin",
  description: "Rol admin",
  isActive: true,
  isSystem: false,
  landingRoute: "/admin/panel",
  permissionsCount: 5,
  usersCount: 3,
  ...overrides,
});

const createClinicOption = (
  overrides: Partial<CentroAtencionListItem> = {},
): CentroAtencionListItem => ({
  id: 1,
  name: "Centro 1",
  folioCode: "CEN-001",
  isExternal: false,
  isActive: true,
  ...overrides,
});

describe("UsersPage UI", () => {
  const refetch = vi.fn();
  const refetchCapabilities = vi.fn();
  const defaultPermissionDeps = {
    hasCapability: () => true,
    hasPermission: () => true,
    hasEffectivePermission: () => true,
  } as ReturnType<typeof usePermissionDependencies>;

  beforeEach(() => {
    const activeUser = createMockUser({
      id: 1,
      fullname: "Juan Perez",
      username: "jperez",
      email: "juan.perez@metro.cdmx.gob.mx",
      isActive: true,
      clinic: { id: 1, name: "Centro 1" },
      primaryRole: "Clinico",
      avatarUrl: null,
    });

    const inactiveUser = createMockUser({
      id: 2,
      fullname: "Roberto Bloqueado",
      username: "banned_user",
      email: "banned@metro.cdmx.gob.mx",
      isActive: false,
      clinic: null,
      primaryRole: "Auditoria",
      avatarUrl: null,
    });

    vi.mocked(useUsersList).mockImplementation((params) => ({
      data: {
        items: [activeUser, inactiveUser],
        page: params?.page ?? 1,
        pageSize: params?.pageSize ?? 10,
        total: 2,
        totalPages: 1,
      },
      isLoading: false,
      error: null,
      isFetching: false,
      refetch,
    }));

    vi.mocked(useRolesList).mockReturnValue({
      data: {
        items: [
          createRoleOption({ id: 1, name: "Clinico" }),
          createRoleOption({ id: 2, name: "Auditoria" }),
        ],
      },
    } as ReturnType<typeof useRolesList>);

    vi.mocked(useCentrosAtencionList).mockReturnValue({
      data: {
        items: [createClinicOption({ id: 1, name: "Centro 1" })],
      },
    } as ReturnType<typeof useCentrosAtencionList>);

    vi.mocked(usePermissionDependencies).mockReturnValue(defaultPermissionDeps);

    vi.mocked(useAuthCapabilities).mockReturnValue({
      isLoading: false,
      isError: false,
      refetch: refetchCapabilities,
    } as ReturnType<typeof useAuthCapabilities>);

    vi.mocked(useAuthSession).mockReturnValue({
      data: { id: 1 },
    } as ReturnType<typeof useAuthSession>);

    userDetailsDialogPropsSpy.mockClear();
  });

  it("renders users table with data", () => {
    render(<UsersPage />);

    expect(screen.getByRole("heading", { name: "Usuarios" })).toBeVisible();
    expect(screen.getByText("Juan Perez")).toBeVisible();
    expect(screen.getByText("jperez")).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Correo" })).toBeVisible();
  });

  it("shows explicit table error description", () => {
    vi.mocked(useUsersList).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new ApiError("USER_NOT_FOUND", "Usuario no encontrado", 404),
      refetch,
    } as ReturnType<typeof useUsersList>);

    render(<UsersPage />);

    expect(screen.getByText("No se pudo cargar usuarios")).toBeVisible();
    expect(
      screen.getByText("El usuario ya no existe o fue eliminado."),
    ).toBeVisible();
  });

  it("opens create dialog from primary action", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    render(<UsersPage />);

    await user.click(screen.getByRole("button", { name: "Nuevo" }));

    expect(screen.getByText("Crear abierto")).toBeVisible();
  });

  it("opens details dialog when clicking a row", async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await user.click(screen.getByText("Juan Perez"));

    expect(screen.getByText("Detalles abiertos")).toBeVisible();
  });

  it("applies status filter and updates query params", async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await user.click(screen.getByRole("button", { name: "Filtros" }));
    await user.click(screen.getByText("Inactivos"));

    // NOTE: useUsersList is also called by UserNotifyDialog (rendered
    // unconditionally by UsersPage) for its recipient-search autocomplete,
    // so we cannot rely on this being the *last* call to the mock. We assert
    // that UsersPage issued a call with the updated filter at some point.
    await waitFor(() => {
      expect(vi.mocked(useUsersList).mock.calls).toContainEqual([
        expect.objectContaining({ status: "inactive" }),
        expect.any(Object),
      ]);
    });
  });

  it("applies pending status filter and updates query params", async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await user.click(screen.getByRole("button", { name: "Filtros" }));
    await user.click(screen.getByText("Pendientes"));

    // See note above: useUsersList has two independent call sites
    // (UsersPage and UserNotifyDialog's recipient autocomplete), so we check
    // that a matching call happened rather than asserting on the last call.
    await waitFor(() => {
      expect(vi.mocked(useUsersList).mock.calls).toContainEqual([
        expect.objectContaining({ status: "pending" }),
        expect.any(Object),
      ]);
    });
  });

  it("updates search query when typing", async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await user.type(screen.getByPlaceholderText("Buscar en la tabla"), "juan");

    // See note above: useUsersList has two independent call sites
    // (UsersPage and UserNotifyDialog's recipient autocomplete), so we check
    // that a matching call happened rather than asserting on the last call.
    await waitFor(() => {
      expect(vi.mocked(useUsersList).mock.calls).toContainEqual([
        expect.objectContaining({ search: "juan" }),
        expect.any(Object),
      ]);
    });
  });

  it("toggles column visibility", async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    // The "Columnas" button shows a badge with the count of currently
    // hidden columns (e.g. "Telefono" is hidden by default), so its
    // accessible name is "Columnas <n>" rather than a bare "Columnas".
    await user.click(screen.getByRole("button", { name: /^Columnas/ }));
    await user.click(screen.getByRole("menuitemcheckbox", { name: "Correo" }));

    await waitFor(() => {
      expect(screen.queryByRole("columnheader", { name: "Correo" })).toBeNull();
    });
  });

  it("does not render an actions column or row action menu", () => {
    render(<UsersPage />);

    expect(
      screen.queryByRole("columnheader", { name: "Acciones" }),
    ).toBeNull();
    expect(screen.queryByLabelText("Acciones")).toBeNull();
  });

  it("opens details in read-only when update permission is missing", async () => {
    const user = userEvent.setup();

    vi.mocked(usePermissionDependencies).mockReturnValue({
      ...defaultPermissionDeps,
      hasCapability: (capabilityKey) => capabilityKey === "admin.users.read",
    });

    render(<UsersPage />);

    await user.click(screen.getByText("Juan Perez"));

    expect(userDetailsDialogPropsSpy).toHaveBeenCalledWith(
      expect.objectContaining({ open: true, canEdit: false }),
    );
  });

  it("passes the credentials capability to the details dialog", async () => {
    const user = userEvent.setup();

    vi.mocked(usePermissionDependencies).mockReturnValue({
      ...defaultPermissionDeps,
      hasCapability: (capabilityKey) =>
        capabilityKey === "admin.users.read" ||
        capabilityKey === "admin.users.update",
    });

    const { unmount } = render(<UsersPage />);
    await user.click(screen.getByText("Juan Perez"));
    expect(userDetailsDialogPropsSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({ open: true, canManageCredentials: false }),
    );
    unmount();

    vi.mocked(usePermissionDependencies).mockReturnValue({
      ...defaultPermissionDeps,
      hasCapability: (capabilityKey) =>
        capabilityKey === "admin.users.read" ||
        capabilityKey === "admin.users.credentials",
    });

    render(<UsersPage />);
    await user.click(screen.getByText("Juan Perez"));
    expect(userDetailsDialogPropsSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({ open: true, canManageCredentials: true }),
    );
  });

  it("passes catalog access flags and enforces update dependencies", async () => {
    const user = userEvent.setup();

    vi.mocked(usePermissionDependencies).mockReturnValue({
      ...defaultPermissionDeps,
      hasCapability: (capabilityKey) =>
        capabilityKey === "admin.users.read" ||
        capabilityKey === "admin.users.update",
    });

    render(<UsersPage />);

    await user.click(screen.getByText("Juan Perez"));

    expect(userDetailsDialogPropsSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        open: true,
        canEdit: true,
        canReadRolesCatalog: false,
        canReadPermissionsCatalog: false,
      }),
    );

    await user.click(screen.getByRole("button", { name: "Filtros" }));
    const filtersMenu = screen.getByRole("menu");
    expect(within(filtersMenu).queryByText("Rol")).toBeNull();
  });

  it("disables users and catalog queries when read capability is denied", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue({
      ...defaultPermissionDeps,
      hasCapability: () => false,
      hasPermission: () => false,
      hasEffectivePermission: () => false,
    });

    render(<UsersPage />);

    expect(vi.mocked(useUsersList)).toHaveBeenLastCalledWith(
      expect.any(Object),
      expect.objectContaining({ enabled: false }),
    );

    expect(vi.mocked(useRolesList)).toHaveBeenLastCalledWith(
      expect.any(Object),
      expect.objectContaining({ enabled: false }),
    );

    expect(vi.mocked(useCentrosAtencionList)).toHaveBeenLastCalledWith(
      expect.any(Object),
      expect.objectContaining({ enabled: false }),
    );
  });

  it("keeps privileged actions disabled while capabilities are loading", () => {
    vi.mocked(useAuthCapabilities).mockReturnValue({
      isLoading: true,
      isError: false,
      refetch: refetchCapabilities,
    } as ReturnType<typeof useAuthCapabilities>);

    render(<UsersPage />);

    expect(screen.queryByRole("button", { name: "Nuevo" })).toBeNull();
    expect(vi.mocked(useUsersList)).toHaveBeenLastCalledWith(
      expect.any(Object),
      expect.objectContaining({ enabled: false }),
    );
  });

  it("shows degraded-safe message and avoids privileged fetches on capabilities error", () => {
    vi.mocked(useAuthCapabilities).mockReturnValue({
      isLoading: false,
      isError: true,
      refetch: refetchCapabilities,
    } as ReturnType<typeof useAuthCapabilities>);

    render(<UsersPage />);

    expect(screen.getByText("No se pudo validar permisos")).toBeVisible();
    expect(
      screen.getByText(
        "Se deshabilitaron acciones de usuarios de forma segura. Reintenta para refrescar capacidades.",
      ),
    ).toBeVisible();
    expect(vi.mocked(useUsersList)).toHaveBeenLastCalledWith(
      expect.any(Object),
      expect.objectContaining({ enabled: false }),
    );
  });
});
