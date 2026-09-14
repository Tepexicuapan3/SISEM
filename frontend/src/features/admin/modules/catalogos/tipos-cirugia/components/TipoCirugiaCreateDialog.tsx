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
import { TipoCirugiaDialogHeader } from "@features/admin/modules/catalogos/tipos-cirugia/components/TipoCirugiaDialogHeader";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createTipoCirugiaSchema,
  type CreateTipoCirugiaFormValues,
} from "@features/admin/modules/catalogos/tipos-cirugia/domain/tipos-cirugia.schemas";
import { useCreateTipoCirugia } from "@features/admin/modules/catalogos/tipos-cirugia/mutations/useCreateTipoCirugia";
import { buildCreateTipoCirugiaPayload } from "@features/admin/modules/catalogos/tipos-cirugia/utils/tipos-cirugia.transform";
import { getTipoCirugiaErrorMessage } from "@features/admin/modules/catalogos/tipos-cirugia/utils/tipos-cirugia.feedback";
import type { CreateTipoCirugiaResponse } from "@api/types";

interface TipoCirugiaCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateTipoCirugiaFormValues = { name: "" };
const FORM_ID = "tipos-cirugia-create-form";

export function TipoCirugiaCreateDialog({ open, onOpenChange }: TipoCirugiaCreateDialogProps) {
  const [createdTipoCirugia, setCreatedTipoCirugia] = useState<CreateTipoCirugiaResponse | null>(null);
  const createTipoCirugia = useCreateTipoCirugia();

  const form = useForm<CreateTipoCirugiaFormValues>({
    resolver: zodResolver(createTipoCirugiaSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedTipoCirugia(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateTipoCirugiaFormValues) => {
    try {
      const result = await createTipoCirugia.mutateAsync({ data: buildCreateTipoCirugiaPayload(values) });
      setCreatedTipoCirugia(result);
      toast.success("Registro creado", { description: `${result.name} se creo correctamente.` });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el registro", {
        description: getTipoCirugiaErrorMessage(error, "Error al crear registro"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo: Tipo de Cirugía</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo registro de tipo de cirugía.
            </DialogDescription>
            <TipoCirugiaDialogHeader
              title="Nuevo: Tipo de Cirugía"
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

              {createdTipoCirugia ? (
                <CatalogCreateResultCard
                  title="Registro creado"
                  description="El registro ya esta disponible en el catalogo."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Nombre", value: createdTipoCirugia.name },
                    { label: "ID", value: createdTipoCirugia.id },
                  ]}
                />
              ) : null}
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={createTipoCirugia.isPending}>Crear</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
