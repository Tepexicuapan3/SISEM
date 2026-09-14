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
import { Switch } from "@shared/ui/switch";
import { MotivoTrasladoDialogHeader } from "@features/admin/modules/catalogos/motivos-traslado/components/MotivoTrasladoDialogHeader";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createMotivoTrasladoSchema,
  type CreateMotivoTrasladoFormValues,
} from "@features/admin/modules/catalogos/motivos-traslado/domain/motivos-traslado.schemas";
import { useCreateMotivoTraslado } from "@features/admin/modules/catalogos/motivos-traslado/mutations/useCreateMotivoTraslado";
import { buildCreateMotivoTrasladoPayload } from "@features/admin/modules/catalogos/motivos-traslado/utils/motivos-traslado.transform";
import { getMotivoTrasladoErrorMessage } from "@features/admin/modules/catalogos/motivos-traslado/utils/motivos-traslado.feedback";
import type { CreateMotivoTrasladoResponse } from "@api/types";

interface MotivoTrasladoCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateMotivoTrasladoFormValues = { name: "", requiresNotes: false };
const FORM_ID = "motivos-traslado-create-form";

export function MotivoTrasladoCreateDialog({ open, onOpenChange }: MotivoTrasladoCreateDialogProps) {
  const [createdMotivoTraslado, setCreatedMotivoTraslado] = useState<CreateMotivoTrasladoResponse | null>(null);
  const createMotivoTraslado = useCreateMotivoTraslado();

  const form = useForm<CreateMotivoTrasladoFormValues>({
    resolver: zodResolver(createMotivoTrasladoSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedMotivoTraslado(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateMotivoTrasladoFormValues) => {
    try {
      const result = await createMotivoTraslado.mutateAsync({ data: buildCreateMotivoTrasladoPayload(values) });
      setCreatedMotivoTraslado(result);
      toast.success("Registro creado", { description: `${result.name} se creo correctamente.` });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el registro", {
        description: getMotivoTrasladoErrorMessage(error, "Error al crear registro"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo motivo de traslado</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo motivo de traslado en ambulancia.
            </DialogDescription>
            <MotivoTrasladoDialogHeader
              title="Nuevo motivo de traslado"
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
                    <FormField
                      control={form.control}
                      name="requiresNotes"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center justify-between rounded-xl border border-line-struct p-3">
                          <div>
                            <FormLabel>Requiere notas adicionales</FormLabel>
                            <p className="text-xs text-txt-muted">
                              Al usar este motivo, la solicitud exigira capturar texto libre (equivalente a "Otro").
                            </p>
                          </div>
                          <FormControl>
                            <Switch checked={field.value} onCheckedChange={field.onChange} />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                  </form>
                </Form>
              </div>

              {createdMotivoTraslado ? (
                <CatalogCreateResultCard
                  title="Registro creado"
                  description="El motivo ya esta disponible en el catalogo."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Nombre", value: createdMotivoTraslado.name },
                    { label: "ID", value: createdMotivoTraslado.id },
                  ]}
                />
              ) : null}
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={createMotivoTraslado.isPending}>Crear</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
