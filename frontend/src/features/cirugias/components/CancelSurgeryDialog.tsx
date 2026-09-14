import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { useMotivoCancelacionCirugiaList } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/useMotivoCancelacionCirugiaList";
import { useCancelSurgery } from "@features/cirugias/mutations/useCancelSurgery";
import {
  cancelSurgerySchema,
  type CancelSurgeryFormInput,
  type CancelSurgeryFormValues,
} from "@features/cirugias/domain/cirugias.schemas";
import { getCirugiasErrorMessage } from "@features/cirugias/utils/cirugias.feedback";
import type { SurgeryItem } from "@api/types";

interface CancelSurgeryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  surgery: SurgeryItem | null;
}

const DEFAULT_VALUES: CancelSurgeryFormInput = { reasonId: 0, notes: "" };
const FORM_ID = "cancel-surgery-form";

export function CancelSurgeryDialog({ open, onOpenChange, surgery }: CancelSurgeryDialogProps) {
  const cancelSurgery = useCancelSurgery();
  const { data: reasonsData } = useMotivoCancelacionCirugiaList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });

  const form = useForm<CancelSurgeryFormInput, unknown, CancelSurgeryFormValues>({
    resolver: zodResolver(cancelSurgerySchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CancelSurgeryFormValues) => {
    if (!surgery) return;
    try {
      await cancelSurgery.mutateAsync({
        id: surgery.id,
        data: { reasonId: values.reasonId, notes: values.notes || undefined },
      });
      toast.success("Cirugia cancelada");
      form.reset(DEFAULT_VALUES);
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo cancelar la cirugia", {
        description: getCirugiasErrorMessage(error, "Error al cancelar cirugia"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>Cancelar cirugia</DialogTitle>
          <DialogDescription>
            {surgery ? `Folio ${surgery.folio}` : "Selecciona el motivo de cancelacion."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="reasonId" render={({ field }) => (
              <FormItem>
                <FormLabel>Motivo</FormLabel>
                <Select value={field.value ? String(field.value) : ""} onValueChange={(v) => field.onChange(Number(v))}>
                  <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Selecciona un motivo" /></SelectTrigger></FormControl>
                  <SelectContent>
                    {(reasonsData?.items ?? []).map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="notes" render={({ field }) => (
              <FormItem>
                <FormLabel>Notas (opcional)</FormLabel>
                <FormControl><Textarea rows={2} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cerrar</Button>
          <Button type="submit" form={FORM_ID} variant="destructive" disabled={cancelSurgery.isPending}>
            Cancelar cirugia
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
