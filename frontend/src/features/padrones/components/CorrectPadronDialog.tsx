import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Textarea } from "@shared/ui/textarea";
import { PadronOptionField } from "@features/padrones/components/PadronOptionField";
import {
  correctPadronSchema,
  todayLocalISO,
  type CorrectPadronFormValues,
} from "@features/padrones/domain/padrones.schemas";
import { useCorrectPadron } from "@features/padrones/queries/usePadrones";
import { getPadronesErrorMessage } from "@features/padrones/utils/padrones.feedback";
import { formatPadronDate } from "@features/padrones/utils/padrones.format";
import type { PadronEnrollment, PadronRegistry } from "@api/types/padrones.types";

interface CorrectPadronDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  registry: PadronRegistry;
  enrollment: PadronEnrollment | null;
}

const ITEM_LABEL: Record<PadronRegistry, string> = {
  cronicos: "Padecimiento correcto (vacío = el mismo)",
  discapacidad: "Discapacidad correcta (vacío = la misma)",
};
const FORM_ID = "correct-padron-form";

const defaultsFor = (enrollment: PadronEnrollment | null): CorrectPadronFormValues => ({
  itemId: "", enrolledOn: "", notes: enrollment?.notes ?? "", detail: "",
});

/**
 * Corrige una inscripción mal capturada (docs/plans/padrones-correccion-y-prioridad.md).
 * No edita: el backend da de baja la original con "Registro erróneo" y crea la nueva.
 */
export function CorrectPadronDialog({ open, onOpenChange, registry, enrollment }: CorrectPadronDialogProps) {
  const correct = useCorrectPadron(registry);
  const form = useForm<CorrectPadronFormValues>({
    resolver: zodResolver(correctPadronSchema),
    defaultValues: defaultsFor(enrollment),
  });

  // Otra fila: las observaciones de partida son las de esa inscripción.
  useEffect(() => {
    form.reset(defaultsFor(enrollment));
  }, [enrollment, form]);

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(defaultsFor(enrollment));
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CorrectPadronFormValues) => {
    if (!enrollment) return;
    try {
      await correct.mutateAsync({
        id: enrollment.id,
        data: {
          itemId: values.itemId || null,
          enrolledOn: values.enrolledOn || null,
          notes: values.notes ?? "",
          detail: values.detail,
        },
      });
      toast.success("Inscripción corregida", {
        description: "La anterior quedó de baja como registro erróneo.",
      });
      handleDialogOpenChange(false);
    } catch (error) {
      toast.error("No se pudo corregir", {
        description: getPadronesErrorMessage(error, "Error al corregir la inscripción"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-160">
        <DialogHeader>
          <DialogTitle>Corregir la inscripción</DialogTitle>
          <DialogDescription>
            La inscripción actual queda dada de baja con motivo "Registro erróneo" y se crea una nueva
            con los datos corregidos. Para otro paciente o centro, da de baja e inscribe de nuevo.
          </DialogDescription>
        </DialogHeader>

        {enrollment ? (
          <div className="rounded-xl border border-line-hairline bg-subtle/50 px-3 py-2 text-sm">
            <p className="font-medium">{enrollment.patientName ?? `Exp. ${enrollment.noExp}`}</p>
            <p className="text-txt-muted">
              Capturado: {enrollment.item.code} — {enrollment.item.description} · inscrito el{" "}
              {formatPadronDate(enrollment.enrolledOn)}
            </p>
          </div>
        ) : null}

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="itemId" render={({ field }) => (
              <FormItem>
                <FormLabel>{ITEM_LABEL[registry]}</FormLabel>
                <FormControl>
                  <PadronOptionField
                    id="padron-correct-item"
                    registry={registry}
                    value={field.value ?? ""}
                    onChange={field.onChange}
                    disabled={correct.isPending}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="enrolledOn" render={({ field }) => (
              <FormItem>
                <FormLabel>Fecha de inscripción (vacío = la misma)</FormLabel>
                <FormControl><Input type="date" max={todayLocalISO()} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="notes" render={({ field }) => (
              <FormItem>
                <FormLabel>Observaciones</FormLabel>
                <FormControl><Textarea rows={2} maxLength={500} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="detail" render={({ field }) => (
              <FormItem>
                <FormLabel>Qué se corrigió</FormLabel>
                <FormControl><Textarea rows={2} maxLength={400} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cerrar</Button>
          <Button type="submit" form={FORM_ID} disabled={correct.isPending}>Corregir</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
