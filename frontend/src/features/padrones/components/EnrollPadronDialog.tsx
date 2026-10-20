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
  enrollPadronSchema,
  todayLocalISO,
  type EnrollPadronFormValues,
} from "@features/padrones/domain/padrones.schemas";
import { useEnrollPadron } from "@features/padrones/queries/usePadrones";
import { getPadronesErrorMessage } from "@features/padrones/utils/padrones.feedback";
import type { PadronRegistry } from "@api/types/padrones.types";

interface EnrollPadronDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  registry: PadronRegistry;
}

const TITLES: Record<PadronRegistry, { title: string; item: string }> = {
  cronicos: { title: "Inscribir al padrón de crónicos", item: "Padecimiento (CIE-10)" },
  discapacidad: { title: "Inscribir al padrón de discapacidad", item: "Discapacidad" },
};

const DEFAULT_VALUES: EnrollPadronFormValues = {
  noExp: "", pkNum: 0, itemId: "", enrolledOn: "", notes: "",
};
const FORM_ID = "enroll-padron-form";

export function EnrollPadronDialog({ open, onOpenChange, registry }: EnrollPadronDialogProps) {
  const enroll = useEnrollPadron(registry);
  const form = useForm<EnrollPadronFormValues>({
    resolver: zodResolver(enrollPadronSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: EnrollPadronFormValues) => {
    try {
      await enroll.mutateAsync({
        noExp: values.noExp.trim(),
        pkNum: Number(values.pkNum ?? 0),
        itemId: values.itemId,
        enrolledOn: values.enrolledOn || null,
        notes: values.notes || null,
      });
      toast.success("Paciente inscrito en el padrón");
      handleDialogOpenChange(false);
    } catch (error) {
      toast.error("No se pudo inscribir", {
        description: getPadronesErrorMessage(error, "Error al inscribir en el padrón"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-160">
        <DialogHeader>
          <DialogTitle>{TITLES[registry].title}</DialogTitle>
          <DialogDescription>
            El centro es el de tu adscripción. Una inscripción activa por paciente y padecimiento.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
              <FormField control={form.control} name="noExp" render={({ field }) => (
                <FormItem>
                  <FormLabel>Expediente</FormLabel>
                  <FormControl><Input {...field} maxLength={20} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="pkNum" render={({ field }) => (
                <FormItem>
                  <FormLabel>Familiar (0 = titular)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      min={0}
                      value={String(field.value ?? 0)}
                      onChange={(e) => field.onChange(e.target.value)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </div>

            <FormField control={form.control} name="itemId" render={({ field }) => (
              <FormItem>
                <FormLabel>{TITLES[registry].item}</FormLabel>
                <FormControl>
                  <PadronOptionField
                    id="padron-item"
                    registry={registry}
                    value={field.value}
                    onChange={field.onChange}
                    disabled={enroll.isPending}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="enrolledOn" render={({ field }) => (
              <FormItem>
                <FormLabel>Fecha de inscripción (vacío = hoy)</FormLabel>
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
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cerrar</Button>
          <Button type="submit" form={FORM_ID} disabled={enroll.isPending}>Inscribir</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
