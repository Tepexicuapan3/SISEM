import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { useMedicosList } from "@features/admin/modules/medicos/hooks/useMedicos";
import { useClinicasList } from "@features/admin/shared/queries/useClinicasList";
import { useTipoCirugiaList } from "@features/admin/modules/catalogos/tipos-cirugia/queries/useTipoCirugiaList";
import { useClasificacionCirugiaList } from "@features/admin/modules/catalogos/clasificaciones-cirugia/queries/useClasificacionCirugiaList";
import { useScheduleSurgery } from "@features/cirugias/mutations/useScheduleSurgery";
import {
  scheduleSurgerySchema,
  type ScheduleSurgeryFormInput,
  type ScheduleSurgeryFormValues,
} from "@features/cirugias/domain/cirugias.schemas";
import { getCirugiasErrorMessage } from "@features/cirugias/utils/cirugias.feedback";

interface ScheduleSurgeryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: ScheduleSurgeryFormInput = {
  noExp: "",
  pkNum: 0,
  surgeonId: 0,
  surgeryTypeId: 0,
  classificationId: 0,
  originClinicId: "",
  scheduledDate: "",
  scheduledTime: "",
  contactPhone: "",
  description: "",
  diagnosisText: "",
  requirements: "",
};

const FORM_ID = "schedule-surgery-form";

export function ScheduleSurgeryDialog({ open, onOpenChange }: ScheduleSurgeryDialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const scheduleSurgery = useScheduleSurgery();

  const { data: medicosData } = useMedicosList(undefined, { enabled: open });
  const { data: clinicasData } = useClinicasList({ enabled: open });
  const { data: surgeryTypesData } = useTipoCirugiaList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });
  const { data: classificationsData } = useClasificacionCirugiaList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });

  const form = useForm<ScheduleSurgeryFormInput, unknown, ScheduleSurgeryFormValues>({
    resolver: zodResolver(scheduleSurgerySchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: ScheduleSurgeryFormValues) => {
    setSubmitting(true);
    try {
      await scheduleSurgery.mutateAsync({
        noExp: values.noExp.trim(),
        pkNum: values.pkNum,
        surgeonId: values.surgeonId,
        surgeryTypeId: values.surgeryTypeId,
        classificationId: values.classificationId,
        originClinicId: values.originClinicId || undefined,
        scheduledDate: values.scheduledDate,
        scheduledTime: values.scheduledTime,
        durationMinutes: values.durationMinutes,
        contactPhone: values.contactPhone || undefined,
        description: values.description || undefined,
        diagnosisText: values.diagnosisText || undefined,
        requirements: values.requirements || undefined,
      });
      toast.success("Cirugia agendada correctamente");
      form.reset(DEFAULT_VALUES);
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo agendar la cirugia", {
        description: getCirugiasErrorMessage(error, "Error al agendar cirugia"),
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[90vw] lg:w-200">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle>Agendar cirugia</DialogTitle>
            <DialogDescription>Captura los datos de la cirugia a agendar.</DialogDescription>
          </DialogHeader>

          <ScrollArea className="flex-1 px-8 pb-8">
            <Form {...form}>
              <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 pt-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField control={form.control} name="noExp" render={({ field }) => (
                    <FormItem>
                      <FormLabel>No. Expediente</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
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
                          name={field.name}
                          onBlur={field.onBlur}
                          ref={field.ref}
                          value={typeof field.value === "number" ? field.value : 0}
                          onChange={(event) => field.onChange(Number(event.target.value))}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                </div>

                <FormField control={form.control} name="surgeonId" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Medico cirujano</FormLabel>
                    <Select value={field.value ? String(field.value) : ""} onValueChange={(v) => field.onChange(Number(v))}>
                      <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Selecciona un medico" /></SelectTrigger></FormControl>
                      <SelectContent>
                        {(medicosData?.items ?? []).map((medico) => (
                          <SelectItem key={medico.id} value={String(medico.id)}>{medico.nombreCompleto}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />

                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField control={form.control} name="surgeryTypeId" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tipo de cirugia</FormLabel>
                      <Select value={field.value ? String(field.value) : ""} onValueChange={(v) => field.onChange(Number(v))}>
                        <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Selecciona un tipo" /></SelectTrigger></FormControl>
                        <SelectContent>
                          {(surgeryTypesData?.items ?? []).map((item) => (
                            <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )} />
                  <FormField control={form.control} name="classificationId" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Clasificacion</FormLabel>
                      <Select value={field.value ? String(field.value) : ""} onValueChange={(v) => field.onChange(Number(v))}>
                        <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Selecciona una clasificacion" /></SelectTrigger></FormControl>
                        <SelectContent>
                          {(classificationsData?.items ?? []).map((item) => (
                            <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )} />
                </div>

                <FormField control={form.control} name="originClinicId" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Clinica de origen (opcional)</FormLabel>
                    <Select value={field.value || ""} onValueChange={field.onChange}>
                      <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Selecciona una clinica" /></SelectTrigger></FormControl>
                      <SelectContent>
                        {(clinicasData?.items ?? []).map((item) => (
                          <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />

                <div className="grid gap-4 sm:grid-cols-3">
                  <FormField control={form.control} name="scheduledDate" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Fecha</FormLabel>
                      <FormControl><Input type="date" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                  <FormField control={form.control} name="scheduledTime" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Hora</FormLabel>
                      <FormControl><Input type="time" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                  <FormField control={form.control} name="durationMinutes" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Duracion (min)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={1}
                          value={typeof field.value === "number" ? field.value : ""}
                          onChange={(event) => field.onChange(event.target.value ? Number(event.target.value) : undefined)}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                </div>

                <FormField control={form.control} name="contactPhone" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Telefono de contacto</FormLabel>
                    <FormControl><Input {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <FormField control={form.control} name="description" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Descripcion</FormLabel>
                    <FormControl><Textarea rows={2} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <FormField control={form.control} name="diagnosisText" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Diagnostico</FormLabel>
                    <FormControl><Textarea rows={2} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <FormField control={form.control} name="requirements" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Requerimientos</FormLabel>
                    <FormControl><Textarea rows={2} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </form>
            </Form>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={submitting}>Agendar</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
