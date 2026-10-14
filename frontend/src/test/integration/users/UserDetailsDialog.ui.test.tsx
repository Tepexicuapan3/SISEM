import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { UserDetailsDialog } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsDialog";
import {
  createMockUser,
  createMockUserDetail,
  createMockUserRole,
} from "@/test/factories/users";
import { useUserDetail } from "@/domains/auth-access/hooks/rbac/users/useUserDetail";
import { usePermissionsCatalog } from "@/domains/auth-access/hooks/rbac/permissions/usePermissionsCatalog";
import { useAddUserOverride } from "@/domains/auth-access/hooks/rbac/users/useAddUserOverride";
import { useAssignRoles } from "@/domains/auth-access/hooks/rbac/users/useAssignRoles";
import { useRemoveUserOverride } from "@/domains/auth-access/hooks/rbac/users/useRemoveUserOverride";
import { useRevokeUserRole } from "@/domains/auth-access/hooks/rbac/users/useRevokeUserRole";
import { useSetPrimaryRole } from "@/domains/auth-access/hooks/rbac/users/useSetPrimaryRole";
import { useUpdateUser } from "@/domains/auth-access/hooks/rbac/users/useUpdateUser";
import { toast } from "sonner";
import type { CentroAtencionListItem, RoleListItem } from "@api/types";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useUserDetail", () => ({
  useUserDetail: vi.fn(),
}));

vi.mock(
  "@/domains/auth-access/hooks/rbac/permissions/usePermissionsCatalog",
  () => ({
    usePermissionsCatalog: vi.fn(),
  }),
);

vi.mock("@/domains/auth-access/hooks/rbac/users/useUpdateUser", () => ({
  useUpdateUser: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useAssignRoles", () => ({
  useAssignRoles: vi.fn(),
}));

vi.mock(
  "@/domains/auth-access/hooks/rbac/users/useSetPrimaryRole",
  () => ({
    useSetPrimaryRole: vi.fn(),
  }),
);

vi.mock(
  "@/domains/auth-access/hooks/rbac/users/useRevokeUserRole",
  () => ({
    useRevokeUserRole: vi.fn(),
  }),
);

vi.mock(
  "@/domains/auth-access/hooks/rbac/users/useAddUserOverride",
  () => ({
    useAddUserOverride: vi.fn(),
  }),
);

vi.mock(
  "@/domains/auth-access/hooks/rbac/users/useRemoveUserOverride",
  () => ({
    useRemoveUserOverride: vi.fn(),
  }),
);

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

describe("UserDetailsDialog UI", () => {
  const refetch = vi.fn();
  const updateMutate = vi.fn();
  const assignRolesMutate = vi.fn();
  const setPrimaryRoleMutate = vi.fn();
  const revokeUserRoleMutate = vi.fn();
  const addOverrideMutate = vi.fn();
  const removeOverrideMutate = vi.fn();
  const onOpenChange = vi.fn();
  const onClose = vi.fn();

  const roleOptions = [
    createRoleOption({ id: 1, name: "Admin" }),
    createRoleOption({ id: 2, name: "Clinico" }),
    createRoleOption({ id: 3, name: "Auditoria" }),
  ];
  const clinicOptions = [createClinicOption({ id: 1, name: "Centro 1" })];

  const userSummary = createMockUser({
    id: 77,
    fullname: "Maria Lopez",
    username: "mlopez",
    email: "mlopez@metro.cdmx.gob.mx",
    isActive: true,
    clinic: { id: 1, name: "Centro 1" },
    primaryRole: "Admin",
  });

  beforeEach(() => {
    vi.mocked(usePermissionsCatalog).mockReturnValue({
      data: { items: [] },
      isLoading: false,
    } as ReturnType<typeof usePermissionsCatalog>);

    vi.mocked(useUpdateUser).mockReturnValue({
      mutateAsync: updateMutate,
      isPending: false,
    } as ReturnType<typeof useUpdateUser>);

    vi.mocked(useAssignRoles).mockReturnValue({
      mutateAsync: assignRolesMutate,
      isPending: false,
    } as ReturnType<typeof useAssignRoles>);

    vi.mocked(useSetPrimaryRole).mockReturnValue({
      mutateAsync: setPrimaryRoleMutate,
      isPending: false,
    } as ReturnType<typeof useSetPrimaryRole>);

    vi.mocked(useRevokeUserRole).mockReturnValue({
      mutateAsync: revokeUserRoleMutate,
      isPending: false,
    } as ReturnType<typeof useRevokeUserRole>);

    vi.mocked(useAddUserOverride).mockReturnValue({
      mutateAsync: addOverrideMutate,
      isPending: false,
    } as ReturnType<typeof useAddUserOverride>);

    vi.mocked(useRemoveUserOverride).mockReturnValue({
      mutateAsync: removeOverrideMutate,
      isPending: false,
    } as ReturnType<typeof useRemoveUserOverride>);

    updateMutate.mockResolvedValue({
      user: createMockUserDetail({ id: 77, email: "mlopez@metro.cdmx.gob.mx" }),
    });
    updateMutate.mockClear();
    assignRolesMutate.mockResolvedValue({ userId: 77, roles: [] });
    setPrimaryRoleMutate.mockResolvedValue({ userId: 77, roles: [] });
    revokeUserRoleMutate.mockResolvedValue({ userId: 77, roles: [] });
    addOverrideMutate.mockResolvedValue({ userId: 77, overrides: [] });
    removeOverrideMutate.mockResolvedValue({ userId: 77, overrides: [] });

    refetch.mockResolvedValue({ data: undefined });
    refetch.mockClear();

    assignRolesMutate.mockClear();
    setPrimaryRoleMutate.mockClear();
    revokeUserRoleMutate.mockClear();
    addOverrideMutate.mockClear();
    removeOverrideMutate.mockClear();

    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
    onOpenChange.mockClear();
    onClose.mockClear();
  });

  it("shows error state and retries", async () => {
    vi.mocked(useUserDetail).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    const user = userEvent.setup();
    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    expect(screen.getByText("No se pudo cargar el usuario")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("saves updated fields", async () => {
    const userDetail = createMockUserDetail({
      id: 77,
      firstName: "Maria",
      paternalName: "Lopez",
      maternalName: "Diaz",
      email: "mlopez@metro.cdmx.gob.mx",
      clinic: { id: 1, name: "Centro 1" },
      primaryRole: "Admin",
      isActive: true,
    });

    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: userDetail,
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    const user = userEvent.setup();
    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    const emailInput = await screen.findByLabelText("Correo");
    await user.clear(emailInput);
    await user.type(emailInput, "nuevo@metro.cdmx.gob.mx");
    refetch.mockResolvedValueOnce({
      data: {
        user: createMockUserDetail({
          id: 77,
          email: "nuevo@metro.cdmx.gob.mx",
        }),
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
    });
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(updateMutate).toHaveBeenCalledWith({
        userId: 77,
        data: { email: "nuevo@metro.cdmx.gob.mx" },
      });
      expect(toast.success).toHaveBeenCalledWith(
        "Cambios guardados",
        expect.any(Object),
      );
    });
  }, 10000);

  it("stages permission changes and applies them only on save", async () => {
    vi.mocked(usePermissionsCatalog).mockReturnValue({
      data: {
        items: [
          {
            id: 901,
            code: "admin:gestion:usuarios:update",
            description: "Actualizar usuarios",
            isSystem: false,
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof usePermissionsCatalog>);

    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: createMockUserDetail({ id: 77, primaryRole: "Admin" }),
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    const user = userEvent.setup();
    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    await user.click(screen.getByRole("tab", { name: /Permisos/i }));
    await user.type(
      screen.getByRole("textbox", { name: /buscar permiso para override/i }),
      "actualizar usuarios",
    );
    await user.click(
      screen.getByRole("option", {
        name: "Agregar override admin:gestion:usuarios:update",
      }),
    );

    expect(addOverrideMutate).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Guardar" })).toBeEnabled();

    refetch.mockResolvedValueOnce({
      data: {
        user: createMockUserDetail({ id: 77, primaryRole: "Admin" }),
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [
          {
            id: 700,
            permissionCode: "admin:gestion:usuarios:update",
            permissionDescription: "Actualizar usuarios",
            effect: "ALLOW",
            expiresAt: null,
            isExpired: false,
            assignedAt: "2024-01-01T00:00:00Z",
            assignedBy: { id: 1, name: "Admin" },
          },
        ],
      },
    });

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(addOverrideMutate).toHaveBeenCalledWith({
        userId: 77,
        data: {
          permissionCode: "admin:gestion:usuarios:update",
          effect: "ALLOW",
          expiresAt: undefined,
        },
      });
    });

    expect(toast.success).toHaveBeenCalledTimes(1);
    expect(toast.success).toHaveBeenCalledWith(
      "Cambios guardados",
      expect.any(Object),
    );
  });

  it("shows account and audit summary data in general tab", () => {
    const userDetail = createMockUserDetail({
      id: 77,
      firstName: "Maria",
      paternalName: "Lopez",
      maternalName: "Diaz",
      email: "mlopez@metro.cdmx.gob.mx",
      clinic: { id: 1, name: "Centro 1" },
      primaryRole: "Admin",
      isActive: true,
    });

    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: userDetail,
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    expect(screen.getByText("Centro de atención")).toBeVisible();
    expect(screen.getByText("Estado de la cuenta")).toBeVisible();
    expect(screen.getByText("Ultimo acceso")).toBeVisible();
    expect(screen.getByText("Ultima IP")).toBeVisible();
    expect(screen.getByText("Creado por")).toBeVisible();
    expect(screen.getByText("Actualizado por")).toBeVisible();
  });

  it("renders read-only mode when user lacks update permission", async () => {
    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: createMockUserDetail({ id: 77 }),
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit={false}
      />,
    );

    expect(
      screen.getByText(
        "Solo lectura: no puedes actualizar este usuario porque no tienes permisos.",
      ),
    ).toBeVisible();
    expect(screen.getByLabelText("Correo")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
  });

  it("shows pending status when terms are not accepted", async () => {
    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: createMockUserDetail({
          id: 77,
          isActive: true,
          termsAccepted: false,
          mustChangePassword: false,
        }),
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    expect(screen.getAllByText("Pendiente").length).toBeGreaterThan(0);
  });

  it("shows contextual notices when catalog read permissions are missing", async () => {
    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: createMockUserDetail({ id: 77 }),
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    const user = userEvent.setup();
    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
        canReadRolesCatalog={false}
        canReadPermissionsCatalog={false}
      />,
    );

    await user.click(screen.getByRole("tab", { name: /Roles/i }));
    expect(
      screen.getByText(/No tienes acceso al catalogo de roles/i),
    ).toBeVisible();

    await user.click(screen.getByRole("tab", { name: /Permisos/i }));
    expect(
      screen.getByText(/No tienes acceso al catalogo de permisos/i),
    ).toBeVisible();
    expect(
      screen.queryByText(/No se pudo cargar el catalogo de permisos/i),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Reintentar catalogo" }),
    ).toBeNull();
    expect(vi.mocked(usePermissionsCatalog)).toHaveBeenLastCalledWith(false);
  });

  it("shows explicit error when permissions catalog fails", async () => {
    const retryCatalog = vi.fn();

    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: createMockUserDetail({ id: 77 }),
        roles: [createMockUserRole({ id: 1, name: "Admin", isPrimary: true })],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    vi.mocked(usePermissionsCatalog).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("forbidden"),
      refetch: retryCatalog,
    } as ReturnType<typeof usePermissionsCatalog>);

    const user = userEvent.setup();
    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    await user.click(screen.getByRole("tab", { name: /Permisos/i }));

    expect(
      screen.getByText(
        "No se pudo cargar el catalogo de permisos. Verifica que tengas admin:gestion:permisos:read.",
      ),
    ).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Reintentar catalogo" }),
    );
    expect(retryCatalog).toHaveBeenCalled();
  });

  it("closes the dialog from footer", async () => {
    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: createMockUserDetail({ id: 77 }),
        roles: [],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    const user = userEvent.setup();
    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onClose).toHaveBeenCalled();
  });

  it("asks for confirmation when closing with unsaved changes", async () => {
    vi.mocked(useUserDetail).mockReturnValue({
      data: {
        user: createMockUserDetail({ id: 77 }),
        roles: [],
        overrides: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useUserDetail>);

    const user = userEvent.setup();
    render(
      <UserDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        userSummary={userSummary}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        canEdit
      />,
    );

    const emailInput = await screen.findByLabelText("Correo");
    await user.clear(emailInput);
    await user.type(emailInput, "dirty@metro.cdmx.gob.mx");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(
      screen.getByRole("heading", { name: "Salir sin guardar" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Salir" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onClose).toHaveBeenCalled();
  });
});
