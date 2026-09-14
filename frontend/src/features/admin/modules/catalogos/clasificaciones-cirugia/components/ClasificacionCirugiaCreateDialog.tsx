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
import { ClasificacionCirugiaDialogHeader } from "@features/admin/modules/catalogos/clasificaciones-cirugia/components/ClasificacionCirugiaDialogHeader";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createClasificacionCirugiaSchema,
  type CreateClasificacionCirugiaFormValues,
} from "@features/admin/modules/catalogos/clasificaciones-cirugia/domain/clasificaciones-cirugia.schemas";
import { useCreateClasificacionCirugia } from "@features/admin/modules/catalogos/clasificaciones-cirugia/mutations/useCreateClasificacionCirugia";
import { buildCreateClasificacionCirugiaPayload } from "@features/admin/modules/catalogos/clasificaciones-cirugia/utils/clasificaciones-cirugia.transform";
import { getClasificacionCirugiaErrorMessage } from "@features/admin/modules/catalogos/clasificaciones-cirugia/utils/clasificaciones-cirugia.feedback";
import type { CreateClasificacionCirugiaResponse } from "@api/types";

interface ClasificacionCirugiaCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateClasificacionCirugiaFormValues = { name: "" };
const FORM_ID = "clasificaciones-cirugia-create-form";

export function ClasificacionCirugiaCreateDialog({ open, onOpenChange }: ClasificacionCirugiaCreateDialogProps) {
  const [createdClasificacionCirugia, setCreatedClasificacionCirugia] = useState<CreateClasificacionCirugiaResponse | null>(null);
  const createClasificacionCirugia = useCreateClasificacionCirugia();

  const form = useForm<CreateClasificacionCirugiaFormValues>({
    resolver: zodResolver(createClasificacionCirugiaSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedClasificacionCirugia(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateClasificacionCirugiaFormValues) => {
    try {
      const result = await createClasificacionCirugia.mutateAsync({ data: buildCreateClasificacionCirugiaPayload(values) });
      setCreatedClasificacionCirugia(result);
      toast.success("Registro creado", { description: `${result.name} se creo correctamente.` });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el registro", {
        description: getClasificacionCirugiaErrorMessage(error, "Error al crear registro"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo: Clasificación de Cirugía</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo registro de clasificación de cirugía.
            </DialogDescription>
            <ClasificacionCirugiaDialogHeader
              title="Nuevo: Clasificación de Cirugía"
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

              {createdClasificacionCirugia ? (
                <CatalogCreateResultCard
                  title="Registro creado"
                  description="El registro ya esta disponible en el catalogo."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Nombre", value: createdClasificacionCirugia.name },
                    { label: "ID", value: createdClasificacionCirugia.id },
                  ]}
                />
              ) : null}
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={createClasificacionCirugia.isPending}>Crear</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
