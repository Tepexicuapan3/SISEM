import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Textarea } from "@shared/ui/textarea";
import { useRejectPrescription } from "@features/autorizacion-recetas/mutations/useRejectPrescription";
import {
  rejectPrescriptionSchema,
  type RejectPrescriptionFormValues,
} from "@features/autorizacion-recetas/domain/prescription-authorizations.schemas";
import { getPrescriptionAuthErrorMessage } from "@features/autorizacion-recetas/utils/prescription-authorizations.feedback";
import { ApiError } from "@api/utils/errors";
import type { PrescriptionAuthorizationItem } from "@api/types";

interface RejectPrescriptionDialogProps {
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

const DEFAULT_VALUES: RejectPrescriptionFormValues = { reason: "" };
const FORM_ID = "reject-prescription-form";

export function RejectPrescriptionDialog({
  open,
  onOpenChange,
  authorization,
}: RejectPrescriptionDialogProps) {
  const rejectPrescription = useRejectPrescription();

  const form = useForm<RejectPrescriptionFormValues>({
    resolver: zodResolver(rejectPrescriptionSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: RejectPrescriptionFormValues) => {
    if (!authorization) return;
    try {
      await rejectPrescription.mutateAsync({ id: authorization.id, reason: values.reason });
      toast.success("Receta rechazada");
      form.reset(DEFAULT_VALUES);
      onOpenChange(false);
    } catch (error) {
      const description = getPrescriptionAuthErrorMessage(error, "Error al rechazar la receta");

      if (error instanceof ApiError && error.code === "AUTHORIZATION_ALREADY_RESOLVED") {
        toast.info(description);
      } else if (error instanceof ApiError && NON_CRITICAL_CODES.has(error.code)) {
        toast.warning(description);
      } else {
        toast.error("No se pudo rechazar la receta", { description });
      }

      // Idem AuthorizePrescriptionDialog: en los codigos mapeados la accion
      // ya no aplica, asi que cerramos. VALIDATION_ERROR (422) no deberia
      // llegar nunca porque zod bloquea el submit antes -- si llegara, deja
      // el dialogo abierto para que el usuario corrija.
      if (error instanceof ApiError && NON_CRITICAL_CODES.has(error.code)) {
        onOpenChange(false);
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>Rechazar receta</DialogTitle>
          <DialogDescription>
            {authorization ? `Expediente ${authorization.noExp}` : "Indica el motivo del rechazo."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="reason" render={({ field }) => (
              <FormItem>
                <FormLabel>Motivo del rechazo</FormLabel>
                <FormControl><Textarea rows={3} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>
            Cerrar
          </Button>
          <Button type="submit" form={FORM_ID} variant="destructive" disabled={rejectPrescription.isPending}>
            Rechazar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
