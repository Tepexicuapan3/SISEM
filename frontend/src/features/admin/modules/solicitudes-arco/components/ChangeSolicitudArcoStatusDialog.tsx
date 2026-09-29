import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { ApiError } from "@api/utils/errors";
import type { ArcoRequestItem } from "@api/types";
import { useChangeSolicitudArcoStatus } from "@features/admin/modules/solicitudes-arco/mutations/useChangeSolicitudArcoStatus";
import {
  changeSolicitudArcoStatusSchema,
  type ChangeSolicitudArcoStatusFormValues,
} from "@features/admin/modules/solicitudes-arco/domain/arco.schemas";
import {
  ARCO_STATUS_LABELS,
  ARCO_TYPE_LABELS,
  formatArcoDate,
} from "@features/admin/modules/solicitudes-arco/domain/arco.labels";
import {
  ARCO_NON_CRITICAL_CODES,
  getArcoErrorMessage,
} from "@features/admin/modules/solicitudes-arco/utils/arco.feedback";

interface ChangeSolicitudArcoStatusDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  solicitud: ArcoRequestItem | null;
}

const FORM_ID = "change-solicitud-arco-status-form";

const defaultValuesFor = (
  solicitud: ArcoRequestItem | null,
): ChangeSolicitudArcoStatusFormValues => ({
  status: solicitud?.status === "recibida" ? "en_proceso" : "procedente",
  response: "",
});

export function ChangeSolicitudArcoStatusDialog({
  open,
  onOpenChange,
  solicitud,
}: ChangeSolicitudArcoStatusDialogProps) {
  const changeStatus = useChangeSolicitudArcoStatus();

  const form = useForm<ChangeSolicitudArcoStatusFormValues>({
    resolver: zodResolver(changeSolicitudArcoStatusSchema),
    defaultValues: defaultValuesFor(solicitud),
  });

  useEffect(() => {
    if (open) form.reset(defaultValuesFor(solicitud));
  }, [open, solicitud, form]);

  const selectedStatus = useWatch({ control: form.control, name: "status" });
  const isResolving = selectedStatus !== "en_proceso";
  const statusOptions =
    solicitud?.status === "recibida"
      ? (["en_proceso", "procedente", "improcedente"] as const)
      : (["procedente", "improcedente"] as const);

  const onSubmit = async (values: ChangeSolicitudArcoStatusFormValues) => {
    if (!solicitud) return;
    try {
      await changeStatus.mutateAsync({
        id: solicitud.id,
        data: {
          status: values.status,
          response: values.status === "en_proceso" ? null : values.response,
        },
      });
      toast.success(`Solicitud ${solicitud.folio}: ${ARCO_STATUS_LABELS[values.status]}`);
      onOpenChange(false);
    } catch (error) {
      const description = getArcoErrorMessage(error, "Error al actualizar la solicitud");
      if (error instanceof ApiError && ARCO_NON_CRITICAL_CODES.has(error.code)) {
        toast.warning(description);
        onOpenChange(false);
      } else {
        toast.error("No se pudo actualizar la solicitud", { description });
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-150">
        <DialogHeader>
          <DialogTitle>Actualizar solicitud {solicitud?.folio}</DialogTitle>
          <DialogDescription>
            {solicitud
              ? `${ARCO_TYPE_LABELS[solicitud.type]} · Expediente ${solicitud.noExp}/${solicitud.pkNum} · Vence ${formatArcoDate(solicitud.dueDate)}`
              : null}
          </DialogDescription>
        </DialogHeader>

        {solicitud ? (
          <p className="rounded-xl bg-subtle p-3 text-sm whitespace-pre-wrap text-txt-body">
            {solicitud.description}
          </p>
        ) : null}

        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="status" render={({ field }) => (
              <FormItem>
                <FormLabel>Nuevo estatus</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                  <SelectContent>
                    {statusOptions.map((value) => (
                      <SelectItem key={value} value={value}>{ARCO_STATUS_LABELS[value]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            {isResolving ? (
              <FormField control={form.control} name="response" render={({ field }) => (
                <FormItem>
                  <FormLabel>Respuesta al solicitante</FormLabel>
                  <FormControl><Textarea rows={4} {...field} /></FormControl>
                  <FormMessage />
                  <p className="text-xs text-txt-muted">
                    Una vez resuelta, la solicitud ya no se puede modificar.
                  </p>
                </FormItem>
              )} />
            ) : null}
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
          <Button
            type="submit"
            form={FORM_ID}
            variant={selectedStatus === "improcedente" ? "destructive" : "default"}
            disabled={changeStatus.isPending}
          >
            {isResolving ? "Resolver" : "Marcar en proceso"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
