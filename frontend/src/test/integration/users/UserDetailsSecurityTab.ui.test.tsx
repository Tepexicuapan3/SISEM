import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { UserDetailsSecurityTab } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsSecurityTab";
import { useActivateUser } from "@/domains/auth-access/hooks/rbac/users/useActivateUser";
import { useDeactivateUser } from "@/domains/auth-access/hooks/rbac/users/useDeactivateUser";
import { useForceLogoutUser } from "@/domains/auth-access/hooks/rbac/users/useForceLogoutUser";
import { useResetUserPassword } from "@/domains/auth-access/hooks/rbac/users/useResetUserPassword";
import { useUnlockUser } from "@/domains/auth-access/hooks/rbac/users/useUnlockUser";
import { toast } from "sonner";
import { ApiError } from "@api/utils/errors";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useActivateUser", () => ({
  useActivateUser: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useDeactivateUser", () => ({
  useDeactivateUser: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useResetUserPassword", () => ({
  useResetUserPassword: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useForceLogoutUser", () => ({
  useForceLogoutUser: vi.fn(),
}));

vi.mock("@/domains/auth-access/hooks/rbac/users/useUnlockUser", () => ({
  useUnlockUser: vi.fn(),
}));

const baseUser = {
  id: 77,
  username: "mlopez",
  fullname: "Maria Lopez",
  email: "mlopez@metro.cdmx.gob.mx",
  isActive: true,
};

describe("UserDetailsSecurityTab UI", () => {
  const activateMutate = vi.fn();
  const deactivateMutate = vi.fn();
  const resetPasswordMutate = vi.fn();
  const forceLogoutMutate = vi.fn();
  const unlockMutate = vi.fn();

  const renderTab = (
    props: Partial<Parameters<typeof UserDetailsSecurityTab>[0]> = {},
  ) =>
    render(
      <UserDetailsSecurityTab
        user={baseUser}
        isSelfUser={false}
        canChangeStatus
        canManageCredentials
        {...props}
      />,
    );

  beforeEach(() => {
    vi.mocked(useActivateUser).mockReturnValue({
      mutateAsync: activateMutate,
      isPending: false,
    } as ReturnType<typeof useActivateUser>);
    vi.mocked(useDeactivateUser).mockReturnValue({
      mutateAsync: deactivateMutate,
      isPending: false,
    } as ReturnType<typeof useDeactivateUser>);
    vi.mocked(useResetUserPassword).mockReturnValue({
      mutateAsync: resetPasswordMutate,
      isPending: false,
    } as ReturnType<typeof useResetUserPassword>);
    vi.mocked(useForceLogoutUser).mockReturnValue({
      mutateAsync: forceLogoutMutate,
      isPending: false,
    } as ReturnType<typeof useForceLogoutUser>);
    vi.mocked(useUnlockUser).mockReturnValue({
      mutateAsync: unlockMutate,
      isPending: false,
    } as ReturnType<typeof useUnlockUser>);

    activateMutate.mockReset().mockResolvedValue({ id: 77, isActive: true });
    deactivateMutate.mockReset().mockResolvedValue({ id: 77, isActive: false });
    resetPasswordMutate.mockReset();
    forceLogoutMutate.mockReset();
    unlockMutate.mockReset();
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
  });

  it("shows only the status section without credentials capability", () => {
    renderTab({ canManageCredentials: false });

    expect(screen.getByText("Estado de la cuenta")).toBeVisible();
    expect(screen.queryByText("Contraseña")).toBeNull();
    expect(screen.queryByText("Sesión")).toBeNull();
    expect(screen.queryByText("Bloqueo")).toBeNull();
  });

  it("shows only credential sections without status permission", () => {
    renderTab({ canChangeStatus: false });

    expect(screen.queryByText("Estado de la cuenta")).toBeNull();
    expect(screen.getByText("Contraseña")).toBeVisible();
    expect(screen.getByText("Sesión")).toBeVisible();
    expect(screen.getByText("Bloqueo")).toBeVisible();
  });

  it("hides password and session sections when the viewed user is the current user", () => {
    renderTab({ isSelfUser: true });

    expect(screen.queryByText("Contraseña")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Generar y mostrar" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Generar y enviar por correo" }),
    ).toBeNull();
    expect(screen.queryByText("Sesión")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Forzar cierre de sesión" }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: "Desbloquear" })).toBeVisible();
  });

  it("deactivates the user after confirming", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole("button", { name: "Desactivar" }));
    expect(
      screen.getByRole("heading", { name: "Desactivar usuario" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Desactivar" }));

    await waitFor(() => {
      expect(deactivateMutate).toHaveBeenCalledWith({ userId: 77 });
      expect(toast.success).toHaveBeenCalledWith("Usuario desactivado");
    });
  });

  it("generates and shows the temporary password", async () => {
    resetPasswordMutate.mockResolvedValue({
      temporaryPassword: "Temp0-Pass!",
      mustChangePassword: true,
    });
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole("button", { name: "Generar y mostrar" }));
    await user.click(screen.getByRole("button", { name: "Restablecer" }));

    await waitFor(() => {
      expect(resetPasswordMutate).toHaveBeenCalledWith({ userId: 77 });
    });
    expect(await screen.findByDisplayValue("Temp0-Pass!")).toBeVisible();
  });

  it("sends the temporary password by email without showing it", async () => {
    resetPasswordMutate.mockResolvedValue({
      emailSent: true,
      mustChangePassword: true,
    });
    const user = userEvent.setup();
    renderTab();

    await user.click(
      screen.getByRole("button", { name: "Generar y enviar por correo" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Restablecer y enviar" }),
    );

    await waitFor(() => {
      expect(resetPasswordMutate).toHaveBeenCalledWith({
        userId: 77,
        sendEmail: true,
      });
      expect(toast.success).toHaveBeenCalledWith(
        "Contraseña temporal enviada a mlopez@metro.cdmx.gob.mx",
      );
    });
    expect(screen.queryByLabelText("Contraseña temporal")).toBeNull();
  });

  it("disables the email option when the user has no email", () => {
    renderTab({ user: { ...baseUser, email: null } });

    expect(
      screen.getByRole("button", { name: "Generar y enviar por correo" }),
    ).toBeDisabled();
    expect(
      screen.getByText("El usuario no tiene correo registrado."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Generar y mostrar" }),
    ).toBeEnabled();
  });

  it("suggests the show option when the email could not be sent", async () => {
    resetPasswordMutate.mockRejectedValue(
      new ApiError("EMAIL_SEND_FAILED", "No se pudo enviar", 502),
    );
    const user = userEvent.setup();
    renderTab();

    await user.click(
      screen.getByRole("button", { name: "Generar y enviar por correo" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Restablecer y enviar" }),
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "No se pudo enviar la contraseña por correo",
        expect.objectContaining({
          description: expect.stringContaining("Generar y mostrar"),
        }),
      );
    });
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("forces logout of another user after confirming", async () => {
    forceLogoutMutate.mockResolvedValue({ id: 77, sessionRevoked: true });
    const user = userEvent.setup();
    renderTab();

    await user.click(
      screen.getByRole("button", { name: "Forzar cierre de sesión" }),
    );
    await user.click(screen.getByRole("button", { name: "Forzar cierre" }));

    await waitFor(() => {
      expect(forceLogoutMutate).toHaveBeenCalledWith({ userId: 77 });
      expect(toast.success).toHaveBeenCalledWith("Sesión del usuario cerrada");
    });
  });

  it("unlocks the user's login", async () => {
    unlockMutate.mockResolvedValue({ id: 77, unlocked: true });
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole("button", { name: "Desbloquear" }));

    await waitFor(() => {
      expect(unlockMutate).toHaveBeenCalledWith({ userId: 77 });
      expect(toast.success).toHaveBeenCalledWith("Usuario desbloqueado");
    });
  });
});
