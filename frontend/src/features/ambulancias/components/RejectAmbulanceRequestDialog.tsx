import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Textarea } from "@shared/ui/textarea";
import { useRejectAmbulanceRequest } from "@features/ambulancias/mutations/useRejectAmbulanceRequest";
import {
  rejectAmbulanceRequestSchema,
  type RejectAmbulanceRequestFormValues,
} from "@features/ambulancias/domain/ambulancias.schemas";
import { getAmbulanciasErrorMessage } from "@features/ambulancias/utils/ambulancias.feedback";
import type { AmbulanceRequestItem } from "@api/types";

interface RejectAmbulanceRequestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  request: AmbulanceRequestItem | null;
}

const DEFAULT_VALUES: RejectAmbulanceRequestFormValues = { notes: "" };
const FORM_ID = "reject-ambulance-request-form";

export function RejectAmbulanceRequestDialog({ open, onOpenChange, request }: RejectAmbulanceRequestDialogProps) {
  const rejectRequest = useRejectAmbulanceRequest();

  const form = useForm<RejectAmbulanceRequestFormValues>({
    resolver: zodResolver(rejectAmbulanceRequestSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: RejectAmbulanceRequestFormValues) => {
    if (!request) return;
    try {
      await rejectRequest.mutateAsync({ id: request.id, data: values });
      toast.success("Solicitud rechazada");
      form.reset(DEFAULT_VALUES);
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo rechazar la solicitud", {
        description: getAmbulanciasErrorMessage(error, "Error al rechazar solicitud"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>Rechazar solicitud de traslado</DialogTitle>
          <DialogDescription>
            {request ? `Folio ${request.folio}` : "Indica el motivo del rechazo."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="notes" render={({ field }) => (
              <FormItem>
                <FormLabel>Motivo del rechazo</FormLabel>
                <FormControl><Textarea rows={3} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cerrar</Button>
          <Button type="submit" form={FORM_ID} variant="destructive" disabled={rejectRequest.isPending}>Rechazar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
