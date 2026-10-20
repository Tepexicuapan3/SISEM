import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { MotivoBajaPadronDialogHeader } from "@features/admin/modules/catalogos/motivos-baja-padron/components/MotivoBajaPadronDialogHeader";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createMotivoBajaPadronSchema,
  type CreateMotivoBajaPadronFormValues,
} from "@features/admin/modules/catalogos/motivos-baja-padron/domain/motivos-baja-padron.schemas";
import { useCreateMotivoBajaPadron } from "@features/admin/modules/catalogos/motivos-baja-padron/mutations/useCreateMotivoBajaPadron";
import { buildCreateMotivoBajaPadronPayload } from "@features/admin/modules/catalogos/motivos-baja-padron/utils/motivos-baja-padron.transform";
import { getMotivoBajaPadronErrorMessage } from "@features/admin/modules/catalogos/motivos-baja-padron/utils/motivos-baja-padron.feedback";
import type { CreateMotivoBajaPadronResponse } from "@api/types";

interface MotivoBajaPadronCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateMotivoBajaPadronFormValues = { name: "" };
const FORM_ID = "motivos-baja-padron-create-form";

export function MotivoBajaPadronCreateDialog({ open, onOpenChange }: MotivoBajaPadronCreateDialogProps) {
  const [createdMotivoBajaPadron, setCreatedMotivoBajaPadron] = useState<CreateMotivoBajaPadronResponse | null>(null);
  const createMotivoBajaPadron = useCreateMotivoBajaPadron();

  const form = useForm<CreateMotivoBajaPadronFormValues>({
    resolver: zodResolver(createMotivoBajaPadronSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedMotivoBajaPadron(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateMotivoBajaPadronFormValues) => {
    try {
      const result = await createMotivoBajaPadron.mutateAsync({ data: buildCreateMotivoBajaPadronPayload(values) });
      setCreatedMotivoBajaPadron(result);
      toast.success("Registro creado", { description: `${result.name} se creo correctamente.` });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el registro", {
        description: getMotivoBajaPadronErrorMessage(error, "Error al crear registro"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo: Motivo de Baja de Padrón</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo registro de motivo de baja de padrón.
            </DialogDescription>
            <MotivoBajaPadronDialogHeader
              title="Nuevo: Motivo de Baja de Padrón"
              subtitle="Configura el nombre"
              status={<Badge variant="outline">Plantilla</Badge>}
            />
          </DialogHeader>

          <ScrollArea className="flex-1 px-8 pb-8">
            <div className="space-y-6 pt-4">
              <div className="rounded-2xl border border-line-struct bg-paper p-4">
                <Form {...form}>
                  <form id={FORM_ID} onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Nombre</FormLabel>
                          <FormControl><Input {...field} /></FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </form>
                </Form>
              </div>

              {createdMotivoBajaPadron ? (
                <CatalogCreateResultCard
                  title="Registro creado"
                  description="El registro ya esta disponible en el catalogo."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Nombre", value: createdMotivoBajaPadron.name },
                    { label: "ID", value: createdMotivoBajaPadron.id },
                  ]}
                />
              ) : null}
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={createMotivoBajaPadron.isPending}>Crear</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
