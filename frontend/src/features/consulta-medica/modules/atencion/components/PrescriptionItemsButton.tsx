import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pill, Loader2, X } from "lucide-react";
import * as z from "zod";
import { ApiError } from "@api/utils/errors";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { useAddPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useAddPrescriptionItem";
import { useCancelPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem";
import type { AllergyWarning } from "@api/types";

const SEVERITY_LABEL: Record<AllergyWarning["severity"], string> = {
  L: "Leve",
  M: "Moderada",
  G: "Grave",
};

const PRESCRIPTION_ITEM_ERROR_MESSAGE: Record<string, string> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para editar la receta.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  CONSULTATION_NOT_FOUND: "Primero guarda el diagnostico de esta consulta.",
  PRESCRIPTION_ITEM_ALREADY_EXISTS: "Ese medicamento ya esta agregado en esta receta.",
  PRESCRIPTION_ITEM_NOT_FOUND: "El item de receta ya no existe.",
  VALIDATION_ERROR: "Revisa los datos capturados.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
};

const FALLBACK_ERROR_MESSAGE = "No se pudo completar la accion. Intenta nuevamente.";

const resolveError = (error: unknown): string => {
  if (!(error instanceof ApiError)) {
    return FALLBACK_ERROR_MESSAGE;
  }
  return (
    PRESCRIPTION_ITEM_ERROR_MESSAGE[error.code] ||
    error.message ||
    FALLBACK_ERROR_MESSAGE
  );
};

const addItemSchema = z.object({
  medicationId: z.string().min(1, { error: "Selecciona un medicamento" }),
  dose: z.string().optional(),
  indications: z.string().trim().min(1, { error: "Ingresa las indicaciones" }),
  quantity: z.number().int().min(1, { error: "Minimo 1" }),
});

type AddItemFormValues = z.infer<typeof addItemSchema>;

const buildDefaultValues = (): AddItemFormValues => ({
  medicationId: "",
  dose: "",
  indications: "",
  quantity: 1,
});

interface PrescriptionItemsButtonProps {
  visitId: number;
  disabled?: boolean;
}

export function PrescriptionItemsButton({
  visitId,
  disabled,
}: PrescriptionItemsButtonProps) {
  const [open, setOpen] = useState(false);
  const [allergyWarning, setAllergyWarning] = useState<AllergyWarning | null>(null);
  const [pendingValues, setPendingValues] = useState<AddItemFormValues | null>(null);

  const { data: itemsData, isLoading: isLoadingItems } = usePrescriptionItems(
    visitId,
    { enabled: open },
  );

  const { data: medicamentos } = useQuery({
    queryKey: ["catalogos", "medicamentos", "options"],
    queryFn: () => medicamentosAPI.getAll({ pageSize: 200, isActive: true }),
    enabled: open,
  });

  const addItem = useAddPrescriptionItem();
  const cancelItem = useCancelPrescriptionItem();

  const form = useForm<AddItemFormValues>({
    resolver: zodResolver(addItemSchema),
    defaultValues: buildDefaultValues(),
  });

  const selectedMedicationId = form.watch("medicationId");
  const selectedMedication = (medicamentos?.items ?? []).find(
    (m) => String(m.id) === selectedMedicationId,
  );

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(buildDefaultValues());
      setAllergyWarning(null);
      setPendingValues(null);
    }
    setOpen(nextOpen);
  };

  const submitItem = async (
    values: AddItemFormValues,
    { acknowledgeAllergyWarning = false }: { acknowledgeAllergyWarning?: boolean } = {},
  ) => {
    const result = await addItem.mutateAsync({
      visitId,
      data: {
        medicationId: Number(values.medicationId),
        quantity: values.quantity,
        indications: values.indications.trim(),
        dose: values.dose?.trim() || undefined,
        acknowledgeAllergyWarning,
      },
    });

    if ("requiresAcknowledgment" in result) {
      // El backend NO creo el item -- el paciente tiene una alergia activa
      // que choca con este medicamento. Se muestra la alerta y se espera
      // confirmacion explicita antes de reenviar (decision del usuario:
      // advertencia con constancia auditada, nunca bloqueo duro).
      setAllergyWarning(result.allergyWarning);
      setPendingValues(values);
      return;
    }

    setAllergyWarning(null);
    setPendingValues(null);
    toast.success(
      result.allergyWarningAcknowledged
        ? "Medicamento agregado (alerta de alergia confirmada)"
        : "Medicamento agregado a la receta",
    );
    form.reset(buildDefaultValues());
  };

  const onSubmit = async (values: AddItemFormValues) => {
    try {
      await submitItem(values);
    } catch (error) {
      toast.error("No se pudo agregar el medicamento", {
        description: resolveError(error),
      });
    }
  };

  const handleConfirmDespiteAllergy = async () => {
    if (!pendingValues) return;
    try {
      await submitItem(pendingValues, { acknowledgeAllergyWarning: true });
    } catch (error) {
      toast.error("No se pudo agregar el medicamento", {
        description: resolveError(error),
      });
    }
  };

  const handleCancelAllergyWarning = () => {
    setAllergyWarning(null);
    setPendingValues(null);
  };

  const handleCancel = async (itemId: number) => {
    try {
      await cancelItem.mutateAsync({ visitId, itemId });
      toast.success("Medicamento quitado de la receta");
    } catch (error) {
      toast.error("No se pudo quitar el medicamento", {
        description: resolveError(error),
      });
    }
  };

  const activeItems = itemsData?.items ?? [];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" disabled={disabled}>
          <Pill className="mr-2 size-4" />
          Receta (catálogo)
          {activeItems.length > 0 ? (
            <Badge variant="secondary" className="ml-2">
              {activeItems.length}
            </Badge>
          ) : null}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Receta estructurada</DialogTitle>
          <DialogDescription>
            Medicamentos del catálogo institucional. Complementa las
            indicaciones de texto libre de "Guardar receta".
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            {isLoadingItems ? (
              <p className="text-sm text-txt-muted">Cargando...</p>
            ) : activeItems.length === 0 ? (
              <p className="text-sm text-txt-muted">
                Sin medicamentos estructurados todavía.
              </p>
            ) : (
              <ul className="space-y-2">
                {activeItems.map((item) => (
                  <li
                    key={item.id}
                    className="flex items-center justify-between rounded-lg border p-2"
                  >
                    <span className="text-sm">
                      <strong>{item.medicationName}</strong>
                      {item.dose ? ` — ${item.dose}` : ""} — {item.indications} (
                      {item.quantity})
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={cancelItem.isPending}
                      onClick={() => handleCancel(item.id)}
                    >
                      <X className="size-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {allergyWarning ? (
            <div className="space-y-2 rounded-lg border border-status-critical/50 bg-status-critical/5 p-3">
              <p className="text-sm font-semibold text-status-critical">
                ⚠️ Alergia registrada: {allergyWarning.substance} (
                {SEVERITY_LABEL[allergyWarning.severity]})
              </p>
              {allergyWarning.reaction ? (
                <p className="text-xs text-txt-muted">{allergyWarning.reaction}</p>
              ) : null}
              <p className="text-xs text-txt-muted">
                El medicamento seleccionado choca con esta alergia. Podés
                continuar si lo consideras clínicamente necesario — quedará
                registrado en la bitácora de auditoría.
              </p>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={handleCancelAllergyWarning}>
                  Cancelar
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={addItem.isPending}
                  onClick={handleConfirmDespiteAllergy}
                >
                  {addItem.isPending ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : null}
                  Agregar de todas formas
                </Button>
              </div>
            </div>
          ) : null}

          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-3 border-t pt-4"
            >
              <FormField
                control={form.control}
                name="medicationId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Medicamento</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecciona un medicamento" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(medicamentos?.items ?? []).map((medicamento) => (
                          <SelectItem key={medicamento.id} value={String(medicamento.id)}>
                            {medicamento.name}
                            {medicamento.presentation ? ` (${medicamento.presentation})` : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selectedMedication?.maxQuantity ? (
                      <p className="text-xs text-txt-muted">
                        Máximo {selectedMedication.maxQuantity} unidades por receta.
                      </p>
                    ) : null}
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-3">
                <FormField
                  control={form.control}
                  name="dose"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Dosis (opcional)</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="quantity"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cantidad</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={1}
                          max={selectedMedication?.maxQuantity ?? undefined}
                          {...field}
                          onChange={(event) =>
                            field.onChange(event.target.valueAsNumber)
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="indications"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Indicaciones</FormLabel>
                    <FormControl>
                      <Input {...field} maxLength={140} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
                  Cerrar
                </Button>
                <Button type="submit" disabled={addItem.isPending}>
                  {addItem.isPending ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : null}
                  Agregar
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </div>
      </DialogContent>
    </Dialog>
  );
}
