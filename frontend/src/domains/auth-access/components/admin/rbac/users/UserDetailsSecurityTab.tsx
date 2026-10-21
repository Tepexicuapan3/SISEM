import { useState, type ReactNode } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import {
  KeyRound,
  LockOpen,
  LogOut,
  Mail,
  UserCheck,
  UserX,
} from "lucide-react";
import { Button } from "@shared/ui/button";
import { ConfirmDestructiveDialog } from "@features/admin/shared/components/ConfirmDestructiveDialog";
import { UserResetPasswordResultDialog } from "@/domains/auth-access/components/admin/rbac/users/UserResetPasswordResultDialog";
import { useActivateUser } from "@/domains/auth-access/hooks/rbac/users/useActivateUser";
import { useDeactivateUser } from "@/domains/auth-access/hooks/rbac/users/useDeactivateUser";
import { useForceLogoutUser } from "@/domains/auth-access/hooks/rbac/users/useForceLogoutUser";
import { useResetUserPassword } from "@/domains/auth-access/hooks/rbac/users/useResetUserPassword";
import { useUnlockUser } from "@/domains/auth-access/hooks/rbac/users/useUnlockUser";
import { usersKeys } from "@/domains/auth-access/hooks/rbac/users/users.keys";
import { getUserErrorMessage } from "@/domains/auth-access/adapters/rbac/users/users.feedback";

interface SecurityTabUser {
  id: number;
  username: string;
  fullname: string;
  email: string | null;
  isActive: boolean;
}

interface UserDetailsSecurityTabProps {
  user: SecurityTabUser;
  isSelfUser: boolean;
  canChangeStatus: boolean;
  canManageCredentials: boolean;
}

type ConfirmAction =
  | "toggle-status"
  | "reset-show"
  | "reset-email"
  | "force-logout";

interface SecuritySectionProps {
  title: string;
  description: string;
  children: ReactNode;
}

function SecuritySection({
  title,
  description,
  children,
}: SecuritySectionProps) {
  return (
    <div className="rounded-2xl border border-line-struct bg-paper p-4">
      <h4 className="text-sm font-semibold text-txt-body">{title}</h4>
      <p className="mt-1 text-xs text-txt-muted">{description}</p>
      <div className="mt-3 space-y-3">{children}</div>
    </div>
  );
}

interface SecurityActionProps {
  description: string;
  hint?: string | null;
  children: ReactNode;
}

function SecurityAction({ description, hint, children }: SecurityActionProps) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <p className="text-sm text-txt-body">{description}</p>
        {hint ? <p className="mt-0.5 text-xs text-txt-muted">{hint}</p> : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function UserDetailsSecurityTab({
  user,
  isSelfUser,
  canChangeStatus,
  canManageCredentials,
}: UserDetailsSecurityTabProps) {
  const queryClient = useQueryClient();
  const activateUser = useActivateUser();
  const deactivateUser = useDeactivateUser();
  const resetUserPassword = useResetUserPassword();
  const forceLogoutUser = useForceLogoutUser();
  const unlockUser = useUnlockUser();

  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(
    null,
  );
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(
    null,
  );
  const [resultOpen, setResultOpen] = useState(false);

  const displayName = user.fullname || user.username;
  const hasEmail = Boolean(user.email);
  const isStatusPending = activateUser.isPending || deactivateUser.isPending;

  const invalidateUser = () => {
    void queryClient.invalidateQueries({ queryKey: usersKeys.list() });
    void queryClient.invalidateQueries({ queryKey: usersKeys.detail(user.id) });
  };

  const handleToggleStatus = async () => {
    try {
      if (user.isActive) {
        await deactivateUser.mutateAsync({ userId: user.id });
        toast.success("Usuario desactivado");
      } else {
        await activateUser.mutateAsync({ userId: user.id });
        toast.success("Usuario activado");
      }
      setConfirmAction(null);
    } catch (error) {
      toast.error("No se pudo actualizar el estado", {
        description: getUserErrorMessage(error, "Error al actualizar estado"),
      });
    }
  };

  const handleResetAndShow = async () => {
    try {
      const result = await resetUserPassword.mutateAsync({ userId: user.id });
      setConfirmAction(null);
      setTemporaryPassword(result.temporaryPassword ?? null);
      setResultOpen(true);
    } catch (error) {
      toast.error("No se pudo restablecer la contraseña", {
        description: getUserErrorMessage(
          error,
          "Error al restablecer la contraseña",
        ),
      });
    }
  };

  const handleResetAndEmail = async () => {
    try {
      await resetUserPassword.mutateAsync({ userId: user.id, sendEmail: true });
      setConfirmAction(null);
      toast.success(`Contraseña temporal enviada a ${user.email}`);
      invalidateUser();
    } catch (error) {
      toast.error("No se pudo enviar la contraseña por correo", {
        description: getUserErrorMessage(
          error,
          "Error al enviar la contraseña por correo",
        ),
      });
    }
  };

  const handleForceLogout = async () => {
    try {
      await forceLogoutUser.mutateAsync({ userId: user.id });
      setConfirmAction(null);
      toast.success("Sesión del usuario cerrada");
    } catch (error) {
      toast.error("No se pudo forzar el cierre de sesión", {
        description: getUserErrorMessage(
          error,
          "Error al forzar el cierre de sesión",
        ),
      });
    }
  };

  const handleUnlock = async () => {
    try {
      await unlockUser.mutateAsync({ userId: user.id });
      toast.success("Usuario desbloqueado");
    } catch (error) {
      toast.error("No se pudo desbloquear al usuario", {
        description: getUserErrorMessage(error, "Error al desbloquear"),
      });
    }
  };

  const handleResultOpenChange = (nextOpen: boolean) => {
    setResultOpen(nextOpen);
    if (!nextOpen) {
      setTemporaryPassword(null);
      invalidateUser();
    }
  };

  const confirmConfig: Record<
    ConfirmAction,
    {
      title: string;
      description: string;
      confirmLabel: string;
      isPending: boolean;
      onConfirm: () => Promise<void>;
    }
  > = {
    "toggle-status": {
      title: user.isActive ? "Desactivar usuario" : "Activar usuario",
      description: user.isActive
        ? `¿Desactivar a ${displayName}? Ya no podrá iniciar sesión.`
        : `¿Activar a ${displayName}? Podrá iniciar sesión nuevamente.`,
      confirmLabel: user.isActive ? "Desactivar" : "Activar",
      isPending: isStatusPending,
      onConfirm: handleToggleStatus,
    },
    "reset-show": {
      title: "Restablecer contraseña",
      description: `¿Restablecer la contraseña de ${displayName}? La contraseña actual dejará de funcionar de inmediato y se mostrará la nueva en pantalla.`,
      confirmLabel: "Restablecer",
      isPending: resetUserPassword.isPending,
      onConfirm: handleResetAndShow,
    },
    "reset-email": {
      title: "Restablecer y enviar por correo",
      description: `¿Restablecer la contraseña de ${displayName} y enviarla a ${user.email}? La contraseña actual dejará de funcionar de inmediato.`,
      confirmLabel: "Restablecer y enviar",
      isPending: resetUserPassword.isPending,
      onConfirm: handleResetAndEmail,
    },
    "force-logout": {
      title: "Forzar cierre de sesión",
      description: `¿Cerrar la sesión de ${displayName}? Se desconectará de inmediato en todos sus dispositivos.`,
      confirmLabel: "Forzar cierre",
      isPending: forceLogoutUser.isPending,
      onConfirm: handleForceLogout,
    },
  };
  const activeConfirm = confirmAction ? confirmConfig[confirmAction] : null;

  return (
    <div className="space-y-4 pb-4">
      {canChangeStatus ? (
        <SecuritySection
          title="Estado de la cuenta"
          description="Controla si el usuario puede iniciar sesión."
        >
          <SecurityAction
            description={
              user.isActive
                ? "La cuenta está activa. Al desactivarla, el usuario no podrá acceder al sistema."
                : "La cuenta está inactiva. Al activarla, el usuario podrá acceder al sistema."
            }
          >
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              disabled={isStatusPending}
              onClick={() => setConfirmAction("toggle-status")}
            >
              {user.isActive ? (
                <UserX className="size-4" />
              ) : (
                <UserCheck className="size-4" />
              )}
              {user.isActive ? "Desactivar" : "Activar"}
            </Button>
          </SecurityAction>
        </SecuritySection>
      ) : null}

      {canManageCredentials ? (
        <>
          {!isSelfUser ? (
            <>
              <SecuritySection
                title="Contraseña"
                description="Genera una contraseña temporal; el usuario deberá cambiarla al iniciar sesión. La contraseña actual y la sesión en curso dejan de valer."
              >
                <SecurityAction description="Genera la contraseña y muéstrala aquí para copiarla y entregarla por un medio seguro.">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    disabled={resetUserPassword.isPending}
                    onClick={() => setConfirmAction("reset-show")}
                  >
                    <KeyRound className="size-4" />
                    Generar y mostrar
                  </Button>
                </SecurityAction>
                <SecurityAction
                  description="Genera la contraseña y envíala al correo registrado del usuario."
                  hint={
                    hasEmail
                      ? user.email
                      : "El usuario no tiene correo registrado."
                  }
                >
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    disabled={!hasEmail || resetUserPassword.isPending}
                    onClick={() => setConfirmAction("reset-email")}
                  >
                    <Mail className="size-4" />
                    Generar y enviar por correo
                  </Button>
                </SecurityAction>
              </SecuritySection>

              <SecuritySection
                title="Sesión"
                description="Cierra la sesión activa del usuario."
              >
                <SecurityAction description="Desconecta al usuario de inmediato en todos sus dispositivos.">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    disabled={forceLogoutUser.isPending}
                    onClick={() => setConfirmAction("force-logout")}
                  >
                    <LogOut className="size-4" />
                    Forzar cierre de sesión
                  </Button>
                </SecurityAction>
              </SecuritySection>
            </>
          ) : null}

          <SecuritySection
            title="Bloqueo"
            description="Las cuentas se bloquean tras varios intentos fallidos de inicio de sesión."
          >
            <SecurityAction description="Quita el bloqueo para que el usuario pueda intentar iniciar sesión de nuevo.">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={unlockUser.isPending}
                onClick={() => void handleUnlock()}
              >
                <LockOpen className="size-4" />
                Desbloquear
              </Button>
            </SecurityAction>
          </SecuritySection>
        </>
      ) : null}

      <ConfirmDestructiveDialog
        open={confirmAction !== null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setConfirmAction(null);
        }}
        title={activeConfirm?.title ?? ""}
        description={activeConfirm?.description ?? ""}
        confirmLabel={activeConfirm?.confirmLabel}
        onConfirm={() => {
          void activeConfirm?.onConfirm();
        }}
        confirmDisabled={activeConfirm?.isPending ?? false}
      />
      <UserResetPasswordResultDialog
        open={resultOpen}
        onOpenChange={handleResultOpenChange}
        temporaryPassword={temporaryPassword}
        username={user.username}
      />
    </div>
  );
}
