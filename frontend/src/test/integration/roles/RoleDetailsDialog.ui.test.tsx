import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { RoleDetailsDialog } from "@/domains/auth-access/components/admin/rbac/roles/RoleDetailsDialog";
import {
  createMockRoleDetail,
  createMockRoleListItem,
  createMockRolePermission,
} from "@/test/factories/roles";
import { useRoleDetail } from "@/domains/auth-access/hooks/rbac/roles/useRoleDetail";
import { usePermissionsCatalog } from "@/domains/auth-access/hooks/rbac/permissions/usePermissionsCatalog";
import { useAssignRolePermissions } from "@/domains/auth-access/hooks/rbac/roles/useAssignRolePermissions";
import { useUpdateRole } from "@/domains/auth-access/hooks/rbac/roles/useUpdateRole";
import { toast } from "sonner";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/domains/auth-access/hooks/rbac/roles/useRoleDetail", () => ({
  useRoleDetail: vi.fn(),
}));

vi.mock(
  "@/domains/auth-access/hooks/rbac/permissions/usePermissionsCatalog",
  () => ({
    usePermissionsCatalog: vi.fn(),
  }),
);

vi.mock("@/domains/auth-access/hooks/rbac/roles/useUpdateRole", () => ({
  useUpdateRole: vi.fn(),
}));

vi.mock(
  "@/domains/auth-access/hooks/rbac/roles/useAssignRolePermissions",
  () => ({
    useAssignRolePermissions: vi.fn(),
  }),
);

describe("RoleDetailsDialog UI", () => {
  const refetch = vi.fn();
  const updateMutate = vi.fn();
  const assignPermissionsMutate = vi.fn();
  const onOpenChange = vi.fn();
  const onClose = vi.fn();

  const roleSummary = createMockRoleListItem({
    id: 77,
    name: "Auditoria",
    description: "Rol auditoria",
    isActive: true,
    isSystem: false,
  });

  beforeEach(() => {
    vi.mocked(usePermissionsCatalog).mockReturnValue({
      data: { items: [] },
      isLoading: false,
    } as ReturnType<typeof usePermissionsCatalog>);

    vi.mocked(useUpdateRole).mockReturnValue({
      mutateAsync: updateMutate,
      isPending: false,
    } as ReturnType<typeof useUpdateRole>);

    vi.mocked(useAssignRolePermissions).mockReturnValue({
      mutateAsync: assignPermissionsMutate,
      isPending: false,
    } as ReturnType<typeof useAssignRolePermissions>);

    updateMutate.mockResolvedValue({
      role: createMockRoleDetail({ id: 77, name: "Auditoria" }),
    });
    assignPermissionsMutate.mockResolvedValue({ roleId: 77, permissions: [] });
    updateMutate.mockClear();
    assignPermissionsMutate.mockClear();
    refetch.mockClear();
    refetch.mockResolvedValue({ data: undefined });
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
    onOpenChange.mockClear();
    onClose.mockClear();
  });

  it("shows error state and retries", async () => {
    vi.mocked(useRoleDetail).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    } as ReturnType<typeof useRoleDetail>);

    const user = userEvent.setup();
    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    expect(screen.getByText("No se pudo cargar el rol")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("renders the matrix tab as 'Permisos por módulo' next to the flat 'Permisos' tab", async () => {
    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: createMockRoleDetail({ id: 77, name: "Auditoria" }),
        permissions: [createMockRolePermission({ id: 1 })],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);

    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    expect(
      screen.getByRole("tab", { name: /^Permisos por módulo/ }),
    ).toBeVisible();
    expect(
      screen.getByRole("tab", { name: /^Permisos(?!\s+por)/ }),
    ).toBeVisible();
    expect(screen.queryByRole("tab", { name: /^Módulos/i })).toBeNull();
  });

  it("saves updated fields", async () => {
    const roleDetail = createMockRoleDetail({
      id: 77,
      name: "Auditoria",
      description: "Rol auditoria",
      landingRoute: "/admin/auditoria",
      isActive: true,
      isSystem: false,
    });

    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: roleDetail,
        permissions: [createMockRolePermission({ id: 1 })],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);
    refetch.mockResolvedValue({
      data: {
        role: { ...roleDetail, name: "Auditoria QA" },
        permissions: [createMockRolePermission({ id: 1 })],
      },
    });

    const user = userEvent.setup();
    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    const nameInput = await screen.findByLabelText("Nombre del rol");
    await user.clear(nameInput);
    await user.type(nameInput, "Auditoria QA");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(updateMutate).toHaveBeenCalledWith({
        roleId: 77,
        data: { name: "Auditoria QA" },
      });
      expect(toast.success).toHaveBeenCalledWith(
        "Cambios guardados",
        expect.any(Object),
      );
    });
  });

  it("stages role status and applies it on save", async () => {
    const roleDetail = createMockRoleDetail({
      id: 77,
      name: "Auditoria",
      description: "Rol auditoria",
      isActive: true,
      isSystem: false,
    });

    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: roleDetail,
        permissions: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);
    refetch.mockResolvedValue({
      data: {
        role: { ...roleDetail, isActive: false },
        permissions: [],
      },
    });

    const user = userEvent.setup();
    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    const statusContainer = screen.getByText("Estado").closest("div");
    expect(statusContainer).not.toBeNull();
    const statusSelect = (statusContainer as HTMLElement).querySelector(
      "[data-slot='select-trigger']",
    );
    expect(statusSelect).not.toBeNull();
    await user.click(statusSelect as HTMLElement);

    const listbox = screen.getByRole("listbox");
    await user.click(within(listbox).getByText("Inactivo"));

    expect(updateMutate).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(updateMutate).toHaveBeenCalledWith({
        roleId: 77,
        data: { isActive: false },
      });
      expect(toast.success).toHaveBeenCalledWith(
        "Cambios guardados",
        expect.any(Object),
      );
    });
  });

  it("stages permissions changes and saves them together", async () => {
    const roleDetail = createMockRoleDetail({
      id: 77,
      name: "Auditoria",
      description: "Rol auditoria",
      isActive: true,
      isSystem: false,
    });

    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: roleDetail,
        permissions: [createMockRolePermission({ id: 1, code: "perm:a" })],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);
    refetch.mockResolvedValue({
      data: {
        role: roleDetail,
        permissions: [
          createMockRolePermission({ id: 1, code: "perm:a" }),
          createMockRolePermission({ id: 2, code: "perm:b" }),
        ],
      },
    });

    vi.mocked(usePermissionsCatalog).mockReturnValue({
      data: {
        items: [
          { id: 1, code: "perm:a", description: "A", isSystem: false },
          { id: 2, code: "perm:b", description: "B", isSystem: false },
        ],
      },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof usePermissionsCatalog>);

    const user = userEvent.setup();
    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    await user.click(screen.getByRole("tab", { name: /^Permisos(?!\s+por)/i }));
    await user.click(
      screen.getByRole("button", { name: "Agregar permiso perm:b" }),
    );

    expect(assignPermissionsMutate).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(assignPermissionsMutate).toHaveBeenCalledWith({
        data: { roleId: 77, permissionIds: [1, 2] },
      });
      expect(toast.success).toHaveBeenCalledWith(
        "Cambios guardados",
        expect.any(Object),
      );
    });
  });

  it("shows read-only notice for system role", async () => {
    const roleDetail = createMockRoleDetail({
      id: 77,
      name: "Admin",
      description: "Rol sistema",
      isActive: true,
      isSystem: true,
    });

    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: roleDetail,
        permissions: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);

    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    expect(
      screen.getByText(
        "Solo lectura: no puedes actualizar este rol porque es de sistema o no tienes permisos.",
      ),
    ).toBeVisible();
  });

  it("shows contextual notice when permissions catalog access is missing", async () => {
    const roleDetail = createMockRoleDetail({
      id: 77,
      name: "Auditoria",
      isSystem: false,
    });

    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: roleDetail,
        permissions: [createMockRolePermission({ id: 1, code: "perm:a" })],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);

    const user = userEvent.setup();
    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
        canReadPermissionsCatalog={false}
      />,
    );

    await user.click(screen.getByRole("tab", { name: /^Permisos(?!\s+por)/i }));

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
    const roleDetail = createMockRoleDetail({
      id: 77,
      name: "Auditoria",
      isSystem: false,
    });

    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: roleDetail,
        permissions: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);

    vi.mocked(usePermissionsCatalog).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("forbidden"),
      refetch: retryCatalog,
    } as ReturnType<typeof usePermissionsCatalog>);

    const user = userEvent.setup();
    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    await user.click(screen.getByRole("tab", { name: /^Permisos(?!\s+por)/i }));

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

  it("asks for confirmation when closing with unsaved changes", async () => {
    const roleDetail = createMockRoleDetail({
      id: 77,
      name: "Auditoria",
      description: "Rol auditoria",
      isSystem: false,
    });

    vi.mocked(useRoleDetail).mockReturnValue({
      data: {
        role: roleDetail,
        permissions: [],
      },
      isLoading: false,
      isError: false,
      refetch,
    } as ReturnType<typeof useRoleDetail>);

    const user = userEvent.setup();
    render(
      <RoleDetailsDialog
        open
        onOpenChange={onOpenChange}
        onClose={onClose}
        roleSummary={roleSummary}
        canEdit
      />,
    );

    const nameInput = await screen.findByLabelText("Nombre del rol");
    await user.clear(nameInput);
    await user.type(nameInput, "Auditoria Editada");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(
      screen.getByRole("heading", { name: "Salir sin guardar" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Salir" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onClose).toHaveBeenCalled();
  });
});
