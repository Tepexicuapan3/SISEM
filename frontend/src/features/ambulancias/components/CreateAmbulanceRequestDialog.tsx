import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Separator } from "@shared/ui/separator";
import { Textarea } from "@shared/ui/textarea";
import { useClinicasList } from "@features/admin/shared/queries/useClinicasList";
import { useParentescoList } from "@features/admin/modules/catalogos/parentescos/queries/useParentescoList";
import { useMotivoTrasladoList } from "@features/admin/modules/catalogos/motivos-traslado/queries/useMotivoTrasladoList";
import { useTipoTrasladoList } from "@features/admin/modules/catalogos/tipos-traslado/queries/useTipoTrasladoList";
import { useTipoServicioAmbulanciaList } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/useTipoServicioAmbulanciaList";
import { useDestinoAmbulanciaList } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/useDestinoAmbulanciaList";
import { useCreateAmbulanceRequest } from "@features/ambulancias/mutations/useCreateAmbulanceRequest";
import {
  createAmbulanceRequestSchema,
  type CreateAmbulanceRequestFormInput,
  type CreateAmbulanceRequestFormValues,
} from "@features/ambulancias/domain/ambulancias.schemas";
import { getAmbulanciasErrorMessage } from "@features/ambulancias/utils/ambulancias.feedback";

interface CreateAmbulanceRequestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateAmbulanceRequestFormInput = {
  noExp: "",
  pkNum: 0,
  requestingClinicId: "",
  requestedByName: "",
  requestedByRelationshipId: "",
  socialWorkNotes: "",
  reasonId: 0,
  reasonNotes: "",
  diagnosisText: "",
  originStreet: "",
  originZip: "",
  originNeighborhood: "",
  originBorough: "",
  originPhone: "",
  originReference: "",
  destinationId: 0,
  schedules: [{ transferDate: "", transferTime: "", transferTypeId: 0, serviceTypeId: 0 }],
};

const FORM_ID = "create-ambulance-request-form";

export function CreateAmbulanceRequestDialog({ open, onOpenChange }: CreateAmbulanceRequestDialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const createRequest = useCreateAmbulanceRequest();

  const { data: clinicasData } = useClinicasList({ enabled: open });
  const { data: parentescosData } = useParentescoList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });
  const { data: reasonsData } = useMotivoTrasladoList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });
  const { data: transferTypesData } = useTipoTrasladoList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });
  const { data: serviceTypesData } = useTipoServicioAmbulanciaList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });
  const { data: destinationsData } = useDestinoAmbulanciaList({ page: 1, pageSize: 200, isActive: true }, { enabled: open });

  const form = useForm<CreateAmbulanceRequestFormInput, unknown, CreateAmbulanceRequestFormValues>({
    resolver: zodResolver(createAmbulanceRequestSchema),
    defaultValues: DEFAULT_VALUES,
  });
  const { fields, append, remove } = useFieldArray({ control: form.control, name: "schedules" });

  const selectedReasonId = form.watch("reasonId");
  const selectedReason = (reasonsData?.items ?? []).find((item) => item.id === Number(selectedReasonId));

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(DEFAULT_VALUES);
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateAmbulanceRequestFormValues) => {
    setSubmitting(true);
    try {
      await createRequest.mutateAsync({
        noExp: values.noExp.trim(),
        pkNum: values.pkNum,
        requestingClinicId: values.requestingClinicId,
        requestedByName: values.requestedByName.trim(),
        requestedByRelationshipId: values.requestedByRelationshipId || undefined,
        socialWorkNotes: values.socialWorkNotes || undefined,
        reasonId: values.reasonId,
        reasonNotes: values.reasonNotes || undefined,
        diagnosisText: values.diagnosisText || undefined,
        originStreet: values.originStreet || undefined,
        originZip: values.originZip || undefined,
        originNeighborhood: values.originNeighborhood || undefined,
        originBorough: values.originBorough || undefined,
        originPhone: values.originPhone || undefined,
        originReference: values.originReference || undefined,
        destinationId: values.destinationId,
        schedules: values.schedules,
      });
      toast.success("Solicitud de traslado registrada");
      form.reset(DEFAULT_VALUES);
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo registrar la solicitud", {
        description: getAmbulanciasErrorMessage(error, "Error al registrar solicitud"),
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle>Nueva solicitud de traslado</DialogTitle>
            <DialogDescription>Captura los datos de la solicitud de traslado en ambulancia.</DialogDescription>
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
                  <FormField control={form.control} name="requestingClinicId" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Clinica solicitante</FormLabel>
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
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField control={form.control} name="requestedByName" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nombre de quien solicita</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                  <FormField control={form.control} name="requestedByRelationshipId" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Parentesco (opcional)</FormLabel>
                      <Select value={field.value || ""} onValueChange={field.onChange}>
                        <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Selecciona un parentesco" /></SelectTrigger></FormControl>
                        <SelectContent>
                          {(parentescosData?.items ?? []).map((item) => (
                            <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )} />
                </div>

                <FormField control={form.control} name="socialWorkNotes" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notas de trabajo social (opcional)</FormLabel>
                    <FormControl><Textarea rows={2} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField control={form.control} name="reasonId" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Motivo de traslado</FormLabel>
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
                  <FormField control={form.control} name="destinationId" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Destino</FormLabel>
                      <Select value={field.value ? String(field.value) : ""} onValueChange={(v) => field.onChange(Number(v))}>
                        <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Selecciona un destino" /></SelectTrigger></FormControl>
                        <SelectContent>
                          {(destinationsData?.items ?? []).map((item) => (
                            <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )} />
                </div>

                {selectedReason?.requiresNotes ? (
                  <FormField control={form.control} name="reasonNotes" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Especifica el motivo</FormLabel>
                      <FormControl><Textarea rows={2} {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                ) : null}

                <FormField control={form.control} name="diagnosisText" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Diagnostico (opcional)</FormLabel>
                    <FormControl><Textarea rows={2} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <Separator />
                <p className="text-sm font-medium text-txt-body">Direccion de origen (opcional)</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField control={form.control} name="originStreet" render={({ field }) => (
                    <FormItem><FormLabel>Calle</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
                  )} />
                  <FormField control={form.control} name="originZip" render={({ field }) => (
                    <FormItem><FormLabel>Codigo Postal</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
                  )} />
                  <FormField control={form.control} name="originNeighborhood" render={({ field }) => (
                    <FormItem><FormLabel>Colonia</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
                  )} />
                  <FormField control={form.control} name="originBorough" render={({ field }) => (
                    <FormItem><FormLabel>Delegacion/Municipio</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
                  )} />
                  <FormField control={form.control} name="originPhone" render={({ field }) => (
                    <FormItem><FormLabel>Telefono</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
                  )} />
                </div>
                <FormField control={form.control} name="originReference" render={({ field }) => (
                  <FormItem><FormLabel>Referencia</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
                )} />

                <Separator />
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-txt-body">Fechas de traslado</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => append({ transferDate: "", transferTime: "", transferTypeId: 0, serviceTypeId: 0 })}
                  >
                    <Plus className="size-4" />
                    Agregar fecha
                  </Button>
                </div>

                {fields.map((item, index) => (
                  <div key={item.id} className="grid gap-4 rounded-xl border border-line-struct p-4 sm:grid-cols-5">
                    <FormField control={form.control} name={`schedules.${index}.transferDate`} render={({ field }) => (
                      <FormItem>
                        <FormLabel>Fecha</FormLabel>
                        <FormControl><Input type="date" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name={`schedules.${index}.transferTime`} render={({ field }) => (
                      <FormItem>
                        <FormLabel>Hora</FormLabel>
                        <FormControl><Input type="time" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name={`schedules.${index}.transferTypeId`} render={({ field }) => (
                      <FormItem>
                        <FormLabel>Tipo de traslado</FormLabel>
                        <Select value={field.value ? String(field.value) : ""} onValueChange={(v) => field.onChange(Number(v))}>
                          <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Tipo" /></SelectTrigger></FormControl>
                          <SelectContent>
                            {(transferTypesData?.items ?? []).map((option) => (
                              <SelectItem key={option.id} value={String(option.id)}>{option.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name={`schedules.${index}.serviceTypeId`} render={({ field }) => (
                      <FormItem>
                        <FormLabel>Tipo de servicio</FormLabel>
                        <Select value={field.value ? String(field.value) : ""} onValueChange={(v) => field.onChange(Number(v))}>
                          <FormControl><SelectTrigger className="w-full"><SelectValue placeholder="Servicio" /></SelectTrigger></FormControl>
                          <SelectContent>
                            {(serviceTypesData?.items ?? []).map((option) => (
                              <SelectItem key={option.id} value={String(option.id)}>{option.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <div className="flex items-end">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        disabled={fields.length <= 1}
                        onClick={() => remove(index)}
                      >
                        <Trash2 className="size-4 text-status-critical" />
                      </Button>
                    </div>
                  </div>
                ))}
              </form>
            </Form>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={submitting}>Registrar solicitud</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
