import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { useAuthorizePrescription } from "@features/autorizacion-recetas/mutations/useAuthorizePrescription";
import { getPrescriptionAuthErrorMessage } from "@features/autorizacion-recetas/utils/prescription-authorizations.feedback";
import { ApiError } from "@api/utils/errors";
import type { PrescriptionAuthorizationItem } from "@api/types";

interface AuthorizePrescriptionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  authorization: PrescriptionAuthorizationItem | null;
}

// Codigos que el backend devuelve como carreras/drift de permiso, no como
// error critico -- ver Requirement "Manejo de Errores" del spec: siempre
// toast no destructivo + refetch, nunca romper la UI.
const NON_CRITICAL_CODES = new Set([
  "AUTHORIZATION_NOT_FOUND",
  "AUTHORIZATION_ALREADY_RESOLVED",
  "SELF_AUTHORIZATION_NOT_ALLOWED",
  "ROLE_NOT_ALLOWED",
]);

export function AuthorizePrescriptionDialog({
  open,
  onOpenChange,
  authorization,
}: AuthorizePrescriptionDialogProps) {
  const authorizePrescription = useAuthorizePrescription();

  const handleConfirm = async () => {
    if (!authorization) return;
    try {
      await authorizePrescription.mutateAsync(authorization.id);
      toast.success("Receta autorizada");
      onOpenChange(false);
    } catch (error) {
      const description = getPrescriptionAuthErrorMessage(error, "Error al autorizar la receta");

      if (error instanceof ApiError && error.code === "AUTHORIZATION_ALREADY_RESOLVED") {
        toast.info(description);
      } else if (error instanceof ApiError && NON_CRITICAL_CODES.has(error.code)) {
        toast.warning(description);
      } else {
        toast.error("No se pudo autorizar la receta", { description });
      }

      // Todos los codigos mapeados dejan la accion sin sentido de reintentar
      // (registro resuelto/inexistente o permiso perdido) -- cerramos el
      // dialogo para no dejar al usuario reintentando algo que ya no aplica.
      if (error instanceof ApiError && NON_CRITICAL_CODES.has(error.code)) {
        onOpenChange(false);
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>Autorizar receta</DialogTitle>
          <DialogDescription>
            {authorization
              ? `Expediente ${authorization.noExp} — ${authorization.medicationsCount} medicamento(s), ${authorization.specializedCount} especial(es), ${authorization.controlledCount} controlado(s).`
              : "Confirma la autorizacion de esta receta."}
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
          <Button
            type="button"
            onClick={() => { void handleConfirm(); }}
            disabled={authorizePrescription.isPending}
          >
            Autorizar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
