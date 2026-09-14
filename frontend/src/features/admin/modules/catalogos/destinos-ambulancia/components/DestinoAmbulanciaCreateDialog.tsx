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
import { DestinoAmbulanciaDialogHeader } from "@features/admin/modules/catalogos/destinos-ambulancia/components/DestinoAmbulanciaDialogHeader";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createDestinoAmbulanciaSchema,
  type CreateDestinoAmbulanciaFormValues,
} from "@features/admin/modules/catalogos/destinos-ambulancia/domain/destinos-ambulancia.schemas";
import { useCreateDestinoAmbulancia } from "@features/admin/modules/catalogos/destinos-ambulancia/mutations/useCreateDestinoAmbulancia";
import { buildCreateDestinoAmbulanciaPayload } from "@features/admin/modules/catalogos/destinos-ambulancia/utils/destinos-ambulancia.transform";
import { getDestinoAmbulanciaErrorMessage } from "@features/admin/modules/catalogos/destinos-ambulancia/utils/destinos-ambulancia.feedback";
import type { CreateDestinoAmbulanciaResponse } from "@api/types";

interface DestinoAmbulanciaCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateDestinoAmbulanciaFormValues = {
  name: "", street: "", zipCode: "", neighborhood: "", borough: "", phone: "", reference: "",
};
const FORM_ID = "destinos-ambulancia-create-form";

export function DestinoAmbulanciaCreateDialog({ open, onOpenChange }: DestinoAmbulanciaCreateDialogProps) {
  const [createdDestino, setCreatedDestino] = useState<CreateDestinoAmbulanciaResponse | null>(null);
  const createDestinoAmbulancia = useCreateDestinoAmbulancia();

  const form = useForm<CreateDestinoAmbulanciaFormValues>({
    resolver: zodResolver(createDestinoAmbulanciaSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedDestino(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateDestinoAmbulanciaFormValues) => {
    try {
      const result = await createDestinoAmbulancia.mutateAsync({ data: buildCreateDestinoAmbulanciaPayload(values) });
      setCreatedDestino(result);
      toast.success("Destino creado", { description: `${result.name} se creo correctamente.` });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el destino", {
        description: getDestinoAmbulanciaErrorMessage(error, "Error al crear destino"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo destino de ambulancia</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo destino de traslado en ambulancia.
            </DialogDescription>
            <DestinoAmbulanciaDialogHeader
              title="Nuevo destino de ambulancia"
              subtitle="Configura el nombre y la direccion"
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
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField
                        control={form.control}
                        name="street"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Calle</FormLabel>
                            <FormControl><Input {...field} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="zipCode"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Codigo Postal</FormLabel>
                            <FormControl><Input {...field} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="neighborhood"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Colonia</FormLabel>
                            <FormControl><Input {...field} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="borough"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Delegacion/Municipio</FormLabel>
                            <FormControl><Input {...field} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="phone"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Telefono</FormLabel>
                            <FormControl><Input {...field} /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <FormField
                      control={form.control}
                      name="reference"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Referencia</FormLabel>
                          <FormControl><Input {...field} /></FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </form>
                </Form>
              </div>

              {createdDestino ? (
                <CatalogCreateResultCard
                  title="Destino creado"
                  description="El destino ya esta disponible en el catalogo."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Nombre", value: createdDestino.name },
                    { label: "ID", value: createdDestino.id },
                  ]}
                />
              ) : null}
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>Cancelar</Button>
              <Button type="submit" form={FORM_ID} disabled={createDestinoAmbulancia.isPending}>Crear destino</Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
