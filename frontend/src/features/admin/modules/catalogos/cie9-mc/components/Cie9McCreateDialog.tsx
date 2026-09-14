import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { Cie9McDialogHeader } from "@features/admin/modules/catalogos/cie9-mc/components/Cie9McDialogHeader";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createCie9McSchema,
  type CreateCie9McFormValues,
} from "@features/admin/modules/catalogos/cie9-mc/domain/cie9-mc.schemas";
import { useCreateCie9Mc } from "@features/admin/modules/catalogos/cie9-mc/mutations/useCreateCie9Mc";
import { buildCreateCie9McPayload } from "@features/admin/modules/catalogos/cie9-mc/utils/cie9-mc.transform";
import { getCie9McErrorMessage } from "@features/admin/modules/catalogos/cie9-mc/utils/cie9-mc.feedback";
import type { CreateCie9McResponse } from "@api/types";

interface Cie9McCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateCie9McFormValues = {
  name: "",
  code: "",
};

const FORM_ID = "cie9-mc-create-form";

export function Cie9McCreateDialog({
  open,
  onOpenChange,
}: Cie9McCreateDialogProps) {
  const [createdCie9Mc, setCreatedCie9Mc] =
    useState<CreateCie9McResponse | null>(null);
  const createCie9Mc = useCreateCie9Mc();

  const form = useForm<CreateCie9McFormValues>({
    resolver: zodResolver(createCie9McSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedCie9Mc(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateCie9McFormValues) => {
    try {
      const result = await createCie9Mc.mutateAsync({
        data: buildCreateCie9McPayload(values),
      });

      setCreatedCie9Mc(result);
      toast.success("Registro creado", {
        description: `El código CIE-9-MC ${result.code} se creó correctamente.`,
      });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el registro", {
        description: getCie9McErrorMessage(error, "Error al crear registro"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo código CIE-9-MC</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo código de procedimiento CIE-9-MC para el catálogo.
            </DialogDescription>
            <Cie9McDialogHeader
              title="Nuevo código CIE-9-MC"
              subtitle="Configura clave y descripción"
              status={<Badge variant="outline">Plantilla</Badge>}
            />
          </DialogHeader>

          <ScrollArea className="flex-1 px-8 pb-8">
            <div className="space-y-6 pt-4">
              <div className="rounded-2xl border border-line-struct bg-paper p-4">
                <Form {...form}>
                  <form
                    id={FORM_ID}
                    onSubmit={form.handleSubmit(onSubmit)}
                    className="space-y-6"
                  >
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField
                        control={form.control}
                        name="code"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Clave</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="name"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Descripción</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </form>
                </Form>
              </div>

              {createdCie9Mc ? (
                <CatalogCreateResultCard
                  title="Código creado"
                  description="El código CIE-9-MC ya está disponible en el catálogo."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Clave", value: createdCie9Mc.code },
                    { label: "Descripción", value: createdCie9Mc.name },
                    { label: "ID", value: createdCie9Mc.id },
                  ]}
                />
              ) : null}
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">
              Completa los campos requeridos.
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleDialogOpenChange(false)}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                form={FORM_ID}
                disabled={createCie9Mc.isPending}
              >
                Crear código
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
