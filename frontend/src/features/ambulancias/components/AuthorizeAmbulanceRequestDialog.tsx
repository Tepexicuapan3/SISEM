import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { useAuthorizeAmbulanceRequest } from "@features/ambulancias/mutations/useAuthorizeAmbulanceRequest";
import {
  authorizeAmbulanceRequestSchema,
  type AuthorizeAmbulanceRequestFormValues,
} from "@features/ambulancias/domain/ambulancias.schemas";
import { getAmbulanciasErrorMessage } from "@features/ambulancias/utils/ambulancias.feedback";
import type { AmbulanceRequestItem } from "@api/types";

interface AuthorizeAmbulanceRequestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  request: AmbulanceRequestItem | null;
}

const DEFAULT_VALUES: AuthorizeAmbulanceRequestFormValues = { serviceNumber: "" };
const FORM_ID = "authorize-ambulance-request-form";

export function AuthorizeAmbulanceRequestDialog({ open, onOpenChange, request }: AuthorizeAmbulanceRequestDialogProps) {
  const authorizeRequest = useAuthorizeAmbulanceRequest();

  const form = useForm<AuthorizeAmbulanceRequestFormValues>({
    resolver: zodResolver(authorizeAmbulanceRequestSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: AuthorizeAmbulanceRequestFormValues) => {
    if (!request) return;
    try {
      await authorizeRequest.mutateAsync({ id: request.id, data: values });
      toast.success("Solicitud autorizada");
      form.reset(DEFAULT_VALUES);
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo autorizar la solicitud", {
        description: getAmbulanciasErrorMessage(error, "Error al autorizar solicitud"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>Autorizar solicitud de traslado</DialogTitle>
          <DialogDescription>
            {request ? `Folio ${request.folio}` : "Indica el numero de servicio/ambulancia."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="serviceNumber" render={({ field }) => (
              <FormItem>
                <FormLabel>Numero de servicio/ambulancia</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cerrar</Button>
          <Button type="submit" form={FORM_ID} disabled={authorizeRequest.isPending}>Autorizar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
