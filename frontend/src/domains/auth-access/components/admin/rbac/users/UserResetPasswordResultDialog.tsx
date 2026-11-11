import { useEffect, useState } from "react";
import { Check, Copy, KeyRound, TriangleAlert } from "lucide-react";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Input } from "@shared/ui/input";

interface UserResetPasswordResultDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  temporaryPassword: string | null;
  username?: string;
}

const COPIED_FEEDBACK_MS = 2000;

/**
 * Muestra la contraseña temporal generada por el reset administrativo.
 *
 * IMPORTANTE: la contraseña solo vive en el estado de este modal (recibida
 * por props desde UsersPage tras la mutación). Nunca se persiste en
 * localStorage, cache de queries ni logs — al cerrarse, el padre descarta
 * el valor.
 */
export function UserResetPasswordResultDialog({
  open,
  onOpenChange,
  temporaryPassword,
  username,
}: UserResetPasswordResultDialogProps) {
  const [copied, setCopied] = useState(false);
  const [prevOpen, setPrevOpen] = useState(open);

  // Al cerrarse se olvida el "copiado", sin un efecto que vuelva a renderizar.
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (!open) setCopied(false);
  }

  useEffect(() => {
    if (!copied) return;
    const timeout = setTimeout(() => setCopied(false), COPIED_FEEDBACK_MS);
    return () => clearTimeout(timeout);
  }, [copied]);

  const handleCopy = async () => {
    if (!temporaryPassword) return;
    try {
      await navigator.clipboard.writeText(temporaryPassword);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="w-[96vw] max-w-none overflow-hidden rounded-3xl bg-paper p-0 sm:max-w-[460px]"
      >
        <DialogHeader className="px-6 pt-6 pb-0">
          <DialogTitle className="flex items-center gap-2 text-base font-semibold">
            <KeyRound className="size-4 text-txt-muted" />
            Contraseña restablecida
          </DialogTitle>
          <DialogDescription className="text-sm text-txt-muted">
            {username
              ? `Nueva contraseña temporal para ${username}.`
              : "Nueva contraseña temporal generada."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 px-6 py-4">
          <div className="space-y-1.5">
            <label
              htmlFor="temporary-password"
              className="text-xs font-medium text-txt-muted"
            >
              Contraseña temporal
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="temporary-password"
                readOnly
                value={temporaryPassword ?? ""}
                className="font-mono"
                onFocus={(event) => event.currentTarget.select()}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-10 shrink-0 gap-1.5"
                onClick={() => void handleCopy()}
              >
                {copied ? (
                  <Check className="size-4 text-status-stable" />
                ) : (
                  <Copy className="size-4" />
                )}
                {copied ? "¡Copiado!" : "Copiar"}
              </Button>
            </div>
          </div>

          <div className="flex items-start gap-2 rounded-xl border border-status-alert/40 bg-status-alert/10 px-3 py-2.5 text-xs font-medium text-status-alert">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            <span>
              Esta contraseña se muestra una sola vez. Compartila con el
              usuario por un medio seguro; deberá cambiarla al iniciar sesión.
            </span>
          </div>
        </div>

        <DialogFooter className="border-t border-line-struct px-6 py-4">
          <Button
            type="button"
            className="w-full sm:w-auto"
            onClick={() => onOpenChange(false)}
          >
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
