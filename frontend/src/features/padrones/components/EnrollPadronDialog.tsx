import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { RadioGroup, RadioGroupItem } from "@shared/ui/radio-group";
import { Textarea } from "@shared/ui/textarea";
import { useDebounce } from "@shared/hooks/useDebounce";
import { PadronOptionField } from "@features/padrones/components/PadronOptionField";
import {
  enrollPadronSchema,
  todayLocalISO,
  type EnrollPadronFormValues,
} from "@features/padrones/domain/padrones.schemas";
import { useEnrollPadron, usePadronFamily } from "@features/padrones/queries/usePadrones";
import { getPadronesErrorMessage } from "@features/padrones/utils/padrones.feedback";
import type { PadronFamilyMember, PadronRegistry } from "@api/types/padrones.types";

interface EnrollPadronDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  registry: PadronRegistry;
}

const TITLES: Record<PadronRegistry, { title: string; item: string }> = {
  cronicos: { title: "Inscribir al padrón de crónicos", item: "Padecimiento (CIE-10)" },
  discapacidad: { title: "Inscribir al padrón de discapacidad", item: "Discapacidad" },
};

// pkNum sin valor hasta elegir a la persona (docs/plans/cronicos-alta-padron.md).
const DEFAULT_VALUES: Partial<EnrollPadronFormValues> = {
  noExp: "", pkNum: undefined, itemId: "", enrolledOn: "", notes: "",
};
const FORM_ID = "enroll-padron-form";
const SEARCH_DELAY_MS = 500;

const relationship = (member: PadronFamilyMember) => {
  if (member.pkNum === 0) return "Titular";
  const text = (member.parentesco ?? "").trim().toLowerCase();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Derechohabiente";
};

const memberSummary = (member: PadronFamilyMember) =>
  [relationship(member), member.edad != null ? `${member.edad} años` : null].filter(Boolean).join(" · ");

export function EnrollPadronDialog({ open, onOpenChange, registry }: EnrollPadronDialogProps) {
  const enroll = useEnrollPadron(registry);
  const form = useForm<EnrollPadronFormValues>({
    resolver: zodResolver(enrollPadronSchema),
    defaultValues: DEFAULT_VALUES,
  });
  const noExp = useWatch({ control: form.control, name: "noExp" }) ?? "";
  const pkNum = useWatch({ control: form.control, name: "pkNum" });
  // Busca solo al dejar de escribir: una peticion por expediente, no por tecla.
  const searchedExp = useDebounce(noExp.trim(), SEARCH_DELAY_MS);
  const isTyping = noExp.trim() !== searchedExp;
  const family = usePadronFamily(searchedExp);
  const members = family.data?.members ?? [];
  const selectedMember = members.find((member) => member.pkNum === pkNum) ?? null;

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: EnrollPadronFormValues) => {
    try {
      await enroll.mutateAsync({
        noExp: values.noExp.trim(),
        pkNum: values.pkNum,
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
            Escribe el expediente y elige a la persona. El centro es el de tu adscripción.
            Una inscripción activa por paciente y padecimiento.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="noExp" render={({ field }) => (
              <FormItem>
                <FormLabel>Expediente</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    maxLength={20}
                    autoComplete="off"
                    onChange={(event) => {
                      field.onChange(event);
                      // Otro expediente: la persona elegida ya no vale.
                      form.resetField("pkNum");
                    }}
                    onKeyDown={(event) => {
                      // Enter no envia el alta a medio escribir el expediente.
                      if (event.key === "Enter") event.preventDefault();
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="pkNum" render={({ field }) => (
              <FormItem>
                <FormLabel>Persona</FormLabel>
                {!noExp.trim() ? (
                  <p className="text-sm text-txt-muted">Escribe el expediente para ver al titular y sus derechohabientes.</p>
                ) : isTyping || family.isFetching ? (
                  <p className="text-sm text-txt-muted">Buscando...</p>
                ) : family.isError ? (
                  <p className="text-sm text-status-critical">
                    {getPadronesErrorMessage(family.error, "No se pudo consultar el expediente")}
                  </p>
                ) : members.length === 0 ? (
                  <p className="text-sm text-txt-muted">El expediente no tiene miembros vigentes.</p>
                ) : (
                  <FormControl>
                    <RadioGroup
                      value={field.value != null ? String(field.value) : ""}
                      onValueChange={(value) => field.onChange(Number(value))}
                      className="gap-1 rounded-xl border border-line-hairline p-2"
                    >
                      {members.map((member) => {
                        const id = `padron-member-${member.pkNum}`;
                        return (
                          <div key={member.pkNum} className="flex items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-subtle">
                            <RadioGroupItem id={id} value={String(member.pkNum)} />
                            <Label htmlFor={id} className="flex flex-1 flex-wrap gap-x-2 font-normal">
                              <span className="font-medium">{member.nombre}</span>
                              <span className="text-txt-muted">{memberSummary(member)}</span>
                            </Label>
                          </div>
                        );
                      })}
                    </RadioGroup>
                  </FormControl>
                )}
                <FormMessage />
              </FormItem>
            )} />

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
                <FormControl>
                  <Input
                    type="date"
                    min={selectedMember?.fechaNac ?? undefined}
                    max={todayLocalISO()}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )} />

            <FormField control={form.control} name="notes" render={({ field }) => (
              <FormItem>
                <FormLabel>Observaciones</FormLabel>
                <FormControl><Textarea rows={2} maxLength={500} {...field} /></FormControl>
                <p className="text-xs text-txt-muted">No captures datos de terceros ni otros diagnósticos.</p>
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
