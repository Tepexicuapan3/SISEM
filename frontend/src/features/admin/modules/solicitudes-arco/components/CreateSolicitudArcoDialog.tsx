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
import { useCreateSolicitudArco } from "@features/admin/modules/solicitudes-arco/mutations/useCreateSolicitudArco";
import {
  createSolicitudArcoSchema,
  type CreateSolicitudArcoFormValues,
} from "@features/admin/modules/solicitudes-arco/domain/arco.schemas";
import {
  ARCO_RELATION_LABELS,
  ARCO_TYPE_LABELS,
  formatArcoDate,
} from "@features/admin/modules/solicitudes-arco/domain/arco.labels";
import { getArcoErrorMessage } from "@features/admin/modules/solicitudes-arco/utils/arco.feedback";

interface CreateSolicitudArcoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const FORM_ID = "create-solicitud-arco-form";

const todayIso = () => {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
};

const buildDefaultValues = (): CreateSolicitudArcoFormValues => ({
  type: "A",
  noExp: "",
  pkNum: "0",
  requesterName: "",
  requesterRelation: "titular",
  requesterEmail: "",
  requesterPhone: "",
  description: "",
  receivedDate: todayIso(),
  transparencyFolio: "",
});

export function CreateSolicitudArcoDialog({ open, onOpenChange }: CreateSolicitudArcoDialogProps) {
  const createSolicitud = useCreateSolicitudArco();

  const form = useForm<CreateSolicitudArcoFormValues>({
    resolver: zodResolver(createSolicitudArcoSchema),
    defaultValues: buildDefaultValues(),
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) form.reset(buildDefaultValues());
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateSolicitudArcoFormValues) => {
    try {
      const created = await createSolicitud.mutateAsync({
        ...values,
        pkNum: Number(values.pkNum),
        requesterEmail: values.requesterEmail || null,
        requesterPhone: values.requesterPhone || null,
        transparencyFolio: values.transparencyFolio || null,
      });
      toast.success(`Solicitud ${created.folio} registrada`, {
        description: `Fecha límite de respuesta: ${formatArcoDate(created.dueDate)}`,
      });
      handleDialogOpenChange(false);
    } catch (error) {
      toast.error("No se pudo registrar la solicitud", {
        description: getArcoErrorMessage(error, "Error al registrar la solicitud"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[85vw] lg:w-180">
        <DialogHeader>
          <DialogTitle>Nueva solicitud ARCO</DialogTitle>
          <DialogDescription>
            Registra una solicitud de acceso, rectificación, cancelación u oposición sobre datos personales.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            id={FORM_ID}
            onSubmit={form.handleSubmit(onSubmit)}
            className="grid max-h-[65vh] grid-cols-1 gap-4 overflow-y-auto pr-1 sm:grid-cols-2"
          >
            <FormField control={form.control} name="type" render={({ field }) => (
              <FormItem>
                <FormLabel>Derecho solicitado</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                  <SelectContent>
                    {Object.entries(ARCO_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="receivedDate" render={({ field }) => (
              <FormItem>
                <FormLabel>Fecha de recepción</FormLabel>
                <FormControl><Input type="date" max={todayIso()} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="noExp" render={({ field }) => (
              <FormItem>
                <FormLabel>Expediente</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="pkNum" render={({ field }) => (
              <FormItem>
                <FormLabel>PK (0 = titular)</FormLabel>
                <FormControl><Input inputMode="numeric" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="requesterName" render={({ field }) => (
              <FormItem>
                <FormLabel>Nombre del solicitante</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="requesterRelation" render={({ field }) => (
              <FormItem>
                <FormLabel>El solicitante es</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                  <SelectContent>
                    {Object.entries(ARCO_RELATION_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="requesterEmail" render={({ field }) => (
              <FormItem>
                <FormLabel>Correo de contacto</FormLabel>
                <FormControl><Input type="email" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="requesterPhone" render={({ field }) => (
              <FormItem>
                <FormLabel>Teléfono de contacto</FormLabel>
                <FormControl><Input {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="transparencyFolio" render={({ field }) => (
              <FormItem>
                <FormLabel>Folio de la Unidad de Transparencia (opcional)</FormLabel>
                <FormControl><Input {...field} maxLength={50} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="description" render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Descripción de la solicitud</FormLabel>
                <FormControl><Textarea rows={4} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </form>
        </Form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" form={FORM_ID} disabled={createSolicitud.isPending}>
            Registrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
