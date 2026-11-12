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
import { Form } from "@shared/ui/form";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { MedicamentoDialogHeader } from "@features/admin/modules/catalogos/medicamentos/components/MedicamentoDialogHeader";
import { MedicamentoFormFields } from "@features/admin/modules/catalogos/medicamentos/components/MedicamentoFormFields";
import { CatalogCreateResultCard } from "@features/admin/modules/catalogos/shared/components/CatalogCreateResultCard";
import {
  createMedicamentoSchema,
  type CreateMedicamentoFormValues,
} from "@features/admin/modules/catalogos/medicamentos/domain/medicamentos.schemas";
import { useCreateMedicamento } from "@features/admin/modules/catalogos/medicamentos/mutations/useCreateMedicamento";
import { buildCreateMedicamentoPayload } from "@features/admin/modules/catalogos/medicamentos/utils/medicamentos.transform";
import { getMedicamentoErrorMessage } from "@features/admin/modules/catalogos/medicamentos/utils/medicamentos.feedback";
import type { CreateMedicamentoResponse } from "@api/types";

interface MedicamentoCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_VALUES: CreateMedicamentoFormValues = {
  name: "",
  code: "",
  genericName: "",
  presentation: "",
  cuadroBasico: "BASICO",
  isControlled: false,
  maxQuantity: "",
};

const FORM_ID = "medicamento-create-form";

export function MedicamentoCreateDialog({ open, onOpenChange }: MedicamentoCreateDialogProps) {
  const [createdMedicamento, setCreatedMedicamento] =
    useState<CreateMedicamentoResponse | null>(null);
  const createMedicamento = useCreateMedicamento();

  const form = useForm<CreateMedicamentoFormValues>({
    resolver: zodResolver(createMedicamentoSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setCreatedMedicamento(null);
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateMedicamentoFormValues) => {
    try {
      const result = await createMedicamento.mutateAsync({
        data: buildCreateMedicamentoPayload(values),
      });

      setCreatedMedicamento(result);
      toast.success("Medicamento creado", {
        description: `El medicamento ${result.name} se creo correctamente.`,
      });
      form.reset(DEFAULT_VALUES);
    } catch (error) {
      toast.error("No se pudo crear el medicamento", {
        description: getMedicamentoErrorMessage(error, "Error al crear medicamento"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nuevo medicamento</DialogTitle>
            <DialogDescription className="sr-only">
              Crea un nuevo medicamento para el catalogo administrativo.
            </DialogDescription>
            <MedicamentoDialogHeader
              title="Nuevo medicamento"
              subtitle="Configura nombre, clave y control"
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
                    <MedicamentoFormFields form={form} />
                  </form>
                </Form>
              </div>

              {createdMedicamento ? (
                <CatalogCreateResultCard
                  title="Medicamento creado"
                  description="El medicamento ya esta disponible para recetar."
                  badgeLabel="Activo"
                  fields={[
                    { label: "Nombre", value: createdMedicamento.name },
                    { label: "ID", value: createdMedicamento.id },
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
                disabled={createMedicamento.isPending}
              >
                Crear medicamento
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
