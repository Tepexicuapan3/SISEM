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
import { TipoServicioAmbulanciaDialogHeader } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/components/TipoServicioAmbulanciaDialogHeader";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createTipoServicioAmbulanciaSchema,
  type CreateTipoServicioAmbulanciaFormValues,
} from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/domain/tipos-servicio-ambulancia.schemas";
import { useCreateTipoServicioAmbulancia } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/mutations/useCreateTipoServicioAmbulancia";
import { buildCreateTipoServicioAmbulanciaPayload } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/utils/tipos-servicio-ambulancia.transform";
import { getTipoServicioAmbulanciaErrorMessage } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/utils/tipos-servicio-ambulancia.feedback";
import type { CreateTipoServicioAmbulanciaResponse } from "@api/types";

interface TipoServicioAmbulanciaCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateTipoServicioAmbulanciaFormValues = { name: "" };
const FORM_ID = "tipos-servicio-ambulancia-create-form";

export function TipoServicioAmbulanciaCreateDialog({ open, onOpenChange }: TipoServicioAmbulanciaCreateDialogProps) {
  const [createdTipoServicioAmbulancia, setCreatedTipoServicioAmbulancia] = useState<CreateTipoServicioAmbulanciaResponse | null>(null);
  const createTipoServicioAmbulancia = useCreateTipoServicioAmbulancia();

  const form = useForm<CreateTipoServicioAmbulanciaFormValues>({
    resolver: zodResolver(createTipoServicioAmbulanciaSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedTipoServicioAmbulancia(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateTipoServicioAmbulanciaFormValues) => {
    try {
      const result = await createTipoServicioAmbulancia.mutateAsync({ data: buildCreateTipoServicioAmbulanciaPayload(values) });
      setCreatedTipoServicioAmbulancia(result);
      toast.success("Registro creado", { description: `${result.name} se creo correctamente.` });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el registro", {
        description: getTipoServicioAmbulanciaErrorMessage(error, "Error al crear registro"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo: Tipo de Servicio de Ambulancia</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo registro de tipo de servicio de ambulancia.
            </DialogDescription>
            <TipoServicioAmbulanciaDialogHeader
              title="Nuevo: Tipo de Servicio de Ambulancia"
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

              {createdTipoServicioAmbulancia ? (
                <CatalogCreateResultCard
                  title="Registro creado"
                  description="El registro ya esta disponible en el catalogo."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Nombre", value: createdTipoServicioAmbulancia.name },
                    { label: "ID", value: createdTipoServicioAmbulancia.id },
                  ]}
                />
              ) : null}
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={createTipoServicioAmbulancia.isPending}>Crear</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
