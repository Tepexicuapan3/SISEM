import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { UserCreateDialog } from "@/domains/auth-access/components/admin/rbac/users/UserCreateDialog";
import { useCreateUser } from "@/domains/auth-access/hooks/rbac/users/useCreateUser";
import { toast } from "sonner";
import type { CentroAtencionListItem, RoleListItem } from "@api/types";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useCreateUser", () => ({
  useCreateUser: vi.fn(),
}));

vi.mock("@shared/ui/select", async () => {
  const React = await import("react");
  const SelectContext = React.createContext({
    value: "",
    onValueChange: () => {},
  });

  const Select = ({ value, onValueChange, children }) => (
    <SelectContext.Provider value={{ value, onValueChange }}>
      <div>{children}</div>
    </SelectContext.Provider>
  );

  const SelectTrigger = ({ children, ...props }) => (
    <button type="button" role="combobox" {...props}>
      {children}
    </button>
  );

  const SelectValue = ({ placeholder }) => <span>{placeholder}</span>;

  const SelectContent = ({ children }) => <div>{children}</div>;

  const SelectItem = ({ value, children }) => {
    const ctx = React.useContext(SelectContext);
    return (
      <button type="button" onClick={() => ctx.onValueChange(value)}>
        {children}
      </button>
    );
  };

  return {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem,
  };
});

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

describe("UserCreateDialog UI", () => {
  const onOpenChange = vi.fn();
  const mutateAsync = vi.fn();

  const roleOptions = [
    createRoleOption({ id: 1, name: "Admin" }),
    createRoleOption({ id: 2, name: "Clinico" }),
  ];
  const clinicOptions = [createClinicOption({ id: 7, name: "Centro Norte" })];

  beforeEach(() => {
    vi.mocked(useCreateUser).mockReturnValue({
      mutateAsync,
      isPending: false,
    } as ReturnType<typeof useCreateUser>);
    onOpenChange.mockReset();
    mutateAsync.mockReset();
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
  });

  it("shows validation errors on empty submit", async () => {
    const user = userEvent.setup();
    render(
      <UserCreateDialog
        open
        onOpenChange={onOpenChange}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Crear usuario" }));

    expect(await screen.findByText("Nombre requerido")).toBeVisible();
    expect(await screen.findByText("Apellido paterno requerido")).toBeVisible();
    expect(await screen.findByText("Usuario requerido")).toBeVisible();
    expect(
      await screen.findByText("Selecciona un rol", { selector: "p" }),
    ).toBeVisible();
    expect(screen.queryByText("Correo invalido")).not.toBeInTheDocument();
  });

  it("submits and closes dialog on success", async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({
      id: 45,
      username: "jperez",
    });

    render(
      <UserCreateDialog
        open
        onOpenChange={onOpenChange}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
      />,
    );

    await user.type(screen.getByLabelText("Nombre"), "Juan");
    await user.type(screen.getByLabelText("Apellido paterno"), "Perez");
    await user.type(screen.getByLabelText("Apellido materno"), "Lopez");
    await user.type(
      screen.getByLabelText("Correo"),
      "jperez@metro.cdmx.gob.mx",
    );
    await user.type(screen.getByLabelText("Usuario"), "jperez");

    await user.click(screen.getByText("Selecciona un centro"));
    await user.click(screen.getByText("Centro Norte"));

    await user.click(screen.getByText("Selecciona un rol"));
    await user.click(screen.getByText("Admin"));

    await user.click(screen.getByRole("button", { name: "Crear usuario" }));

    await waitFor(() => {
      // objectContaining: el formulario además manda los campos opcionales
      // (escuela, sexo, fecha de nacimiento, tipo de personal, ...) en null;
      // aquí solo importan los que se capturaron.
      expect(mutateAsync).toHaveBeenCalledWith({
        data: expect.objectContaining({
          username: "jperez",
          firstName: "Juan",
          paternalName: "Perez",
          maternalName: "Lopez",
          email: "jperez@metro.cdmx.gob.mx",
          clinicId: 7,
          primaryRoleId: 1,
        }),
      });
    });

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
    expect(toast.success).toHaveBeenCalledWith(
      "Usuario creado",
      expect.objectContaining({
        description: expect.stringContaining("jperez"),
      }),
    );
  });

  it("shows error toast when creation fails", async () => {
    const user = userEvent.setup();
    mutateAsync.mockRejectedValueOnce(new Error("boom"));

    render(
      <UserCreateDialog
        open
        onOpenChange={onOpenChange}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
      />,
    );

    await user.type(screen.getByLabelText("Nombre"), "Juan");
    await user.type(screen.getByLabelText("Apellido paterno"), "Perez");
    await user.type(
      screen.getByLabelText("Correo"),
      "jperez@metro.cdmx.gob.mx",
    );
    await user.type(screen.getByLabelText("Usuario"), "jperez");
    await user.click(screen.getByText("Selecciona un rol"));
    await user.click(screen.getByText("Admin"));
    await user.click(screen.getByRole("button", { name: "Crear usuario" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "No se pudo crear el usuario",
        expect.any(Object),
      );
    });
  });
});
