import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
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
import { useUpdatePrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useUpdatePrescriptionItem";
import { PrescriptionItemFields } from "@features/consulta-medica/modules/atencion/components/PrescriptionItemFields";
import { resolvePrescriptionItemError } from "@features/consulta-medica/modules/atencion/domain/prescription-item-errors";
import {
  prescriptionItemFieldsSchema,
  prescriptionItemFieldsToPayload,
  prescriptionItemToFields,
  type PrescriptionItemFieldsValues,
} from "@features/consulta-medica/modules/atencion/domain/prescription-item-form";
import type { PrescriptionItem } from "@api/types";

interface PrescriptionItemEditDialogProps {
  visitId: number;
  item: PrescriptionItem;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Corrige un renglon ya agregado sin quitarlo (el medicamento no cambia). */
export function PrescriptionItemEditDialog({
  visitId,
  item,
  open,
  onOpenChange,
}: PrescriptionItemEditDialogProps) {
  const updateItem = useUpdatePrescriptionItem();
  const form = useForm<PrescriptionItemFieldsValues>({
    resolver: zodResolver(prescriptionItemFieldsSchema),
    values: prescriptionItemToFields(item),
  });

  const onSubmit = async (values: PrescriptionItemFieldsValues) => {
    try {
      await updateItem.mutateAsync({
        visitId,
        itemId: item.id,
        data: prescriptionItemFieldsToPayload(values),
      });
      toast.success("Medicamento corregido");
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo corregir el medicamento", {
        description: resolvePrescriptionItemError(error),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="break-words">Corregir {item.medicationName}</DialogTitle>
          <DialogDescription>
            Para cambiar el medicamento, quítalo y agrega otro.
            {item.requiresAuthorization
              ? " Al ser especial o controlado, la receta se vuelve a autorizar."
              : ""}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <PrescriptionItemFields form={form} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={updateItem.isPending}>
                {updateItem.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                Guardar cambios
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
