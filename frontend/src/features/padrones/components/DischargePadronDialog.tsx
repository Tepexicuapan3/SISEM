import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { useMotivoBajaPadronList } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/useMotivoBajaPadronList";
import {
  dischargePadronSchema,
  todayLocalISO,
  type DischargePadronFormValues,
} from "@features/padrones/domain/padrones.schemas";
import { useDischargePadron } from "@features/padrones/queries/usePadrones";
import { getPadronesErrorMessage } from "@features/padrones/utils/padrones.feedback";
import type { PadronEnrollment, PadronRegistry } from "@api/types/padrones.types";

interface DischargePadronDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  registry: PadronRegistry;
  enrollment: PadronEnrollment | null;
}

const DEFAULT_VALUES: DischargePadronFormValues = { reasonId: 0, detail: "", dischargedOn: "" };
const FORM_ID = "discharge-padron-form";

export function DischargePadronDialog({ open, onOpenChange, registry, enrollment }: DischargePadronDialogProps) {
  const discharge = useDischargePadron(registry);
  const { data: reasons } = useMotivoBajaPadronList({ pageSize: 100, isActive: true }, { enabled: open });
  const form = useForm<DischargePadronFormValues>({
    resolver: zodResolver(dischargePadronSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: DischargePadronFormValues) => {
    if (!enrollment) return;
    try {
      await discharge.mutateAsync({
        id: enrollment.id,
        data: {
          reasonId: Number(values.reasonId),
          detail: values.detail || null,
          dischargedOn: values.dischargedOn || null,
        },
      });
      toast.success("Inscripción dada de baja");
      handleDialogOpenChange(false);
    } catch (error) {
      toast.error("No se pudo dar de baja", {
        description: getPadronesErrorMessage(error, "Error al dar de baja la inscripción"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>Dar de baja la inscripción</DialogTitle>
          <DialogDescription>
            {enrollment
              ? `${enrollment.patientName ?? enrollment.noExp} — ${enrollment.item.description}. Solo se da de baja este padecimiento; queda en el historial.`
              : "Indica el motivo de la baja."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="reasonId" render={({ field }) => (
              <FormItem>
                <FormLabel>Motivo</FormLabel>
                <Select
                  value={field.value ? String(field.value) : ""}
                  onValueChange={(v) => field.onChange(Number(v))}
                >
                  <FormControl>
                    <SelectTrigger><SelectValue placeholder="Selecciona un motivo" /></SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {(reasons?.items ?? []).map((reason) => (
                      <SelectItem key={reason.id} value={String(reason.id)}>{reason.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="dischargedOn" render={({ field }) => (
              <FormItem>
                <FormLabel>Fecha de baja (vacío = hoy)</FormLabel>
                <FormControl><Input type="date" max={todayLocalISO()} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="detail" render={({ field }) => (
              <FormItem>
                <FormLabel>Detalle</FormLabel>
                <FormControl><Textarea rows={2} maxLength={500} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cerrar</Button>
          <Button type="submit" form={FORM_ID} variant="destructive" disabled={discharge.isPending}>
            Dar de baja
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
