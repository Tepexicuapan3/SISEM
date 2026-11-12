import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Plus } from "lucide-react";
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
import { Form } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { useDebounce } from "@shared/hooks/useDebounce";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { useAddPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useAddPrescriptionItem";
import { MedicationControlBadges } from "@features/consulta-medica/modules/atencion/components/MedicationControlBadges";
import { PrescriptionItemsList } from "@features/consulta-medica/modules/atencion/components/PrescriptionItemsList";
import { activePrescriptionItems } from "@features/consulta-medica/modules/atencion/domain/prescription-items";
import { resolvePrescriptionItemError } from "@features/consulta-medica/modules/atencion/domain/prescription-item-errors";
import { PrescriptionItemFields } from "@features/consulta-medica/modules/atencion/components/PrescriptionItemFields";
import {
  addPrescriptionItemSchema,
  emptyPrescriptionItemFields,
  prescriptionItemFieldsToPayload,
  type AddPrescriptionItemFormValues,
} from "@features/consulta-medica/modules/atencion/domain/prescription-item-form";
import type { AllergyWarning, MedicamentoListItem } from "@api/types";

const SEVERITY_LABEL: Record<NonNullable<AllergyWarning["severity"]>, string> = {
  L: "Leve",
  M: "Moderada",
  G: "Grave",
};

const MIN_SEARCH_LENGTH = 2;
const SEARCH_PAGE_SIZE = 20;

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
  const [pendingValues, setPendingValues] = useState<AddPrescriptionItemFormValues | null>(null);
  const [search, setSearch] = useState("");
  const [selectedMedication, setSelectedMedication] = useState<MedicamentoListItem | null>(null);
  const debouncedSearch = useDebounce(search.trim(), 300);

  const { data: itemsData, isLoading: isLoadingItems } = usePrescriptionItems(
    visitId,
    { enabled: open },
  );

  // Busqueda en el servidor (nombre, generico o clave): el catalogo completo
  // no cabe en una sola pagina.
  const shouldSearch = open && !selectedMedication && debouncedSearch.length >= MIN_SEARCH_LENGTH;
  const medicationSearch = useQuery({
    queryKey: ["catalogos", "medicamentos", "search", debouncedSearch],
    queryFn: () =>
      medicamentosAPI.getAll({ search: debouncedSearch, isActive: true, pageSize: SEARCH_PAGE_SIZE }),
    enabled: shouldSearch,
  });
  const searchResults = medicationSearch.data?.items ?? [];

  const addItem = useAddPrescriptionItem();

  const form = useForm<AddPrescriptionItemFormValues>({
    resolver: zodResolver(addPrescriptionItemSchema),
    defaultValues: { medicationId: "", ...emptyPrescriptionItemFields() },
  });

  const resetForm = () => {
    form.reset({ medicationId: "", ...emptyPrescriptionItemFields() });
    setSelectedMedication(null);
    setSearch("");
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      resetForm();
      setAllergyWarning(null);
      setPendingValues(null);
    }
    setOpen(nextOpen);
  };

  const selectMedication = (medication: MedicamentoListItem | null) => {
    setSelectedMedication(medication);
    form.setValue("medicationId", medication ? String(medication.id) : "", {
      shouldValidate: Boolean(medication),
    });
  };

  const submitItem = async (
    values: AddPrescriptionItemFormValues,
    { acknowledgeAllergyWarning = false }: { acknowledgeAllergyWarning?: boolean } = {},
  ) => {
    const result = await addItem.mutateAsync({
      visitId,
      data: {
        medicationId: Number(values.medicationId),
        ...prescriptionItemFieldsToPayload(values),
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
    resetForm();
  };

  const onSubmit = async (values: AddPrescriptionItemFormValues) => {
    try {
      await submitItem(values);
    } catch (error) {
      toast.error("No se pudo agregar el medicamento", {
        description: resolvePrescriptionItemError(error),
      });
    }
  };

  const handleConfirmDespiteAllergy = async () => {
    if (!pendingValues) return;
    try {
      await submitItem(pendingValues, { acknowledgeAllergyWarning: true });
    } catch (error) {
      toast.error("No se pudo agregar el medicamento", {
        description: resolvePrescriptionItemError(error),
      });
    }
  };

  const handleCancelAllergyWarning = () => {
    setAllergyWarning(null);
    setPendingValues(null);
  };

  const activeItems = activePrescriptionItems(itemsData?.items);
  const medicationError = form.formState.errors.medicationId?.message;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" disabled={disabled}>
          <Plus className="mr-2 size-4" />
          Agregar medicamento
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            Medicamentos de la receta
            {activeItems[0]?.prescriptionFolio ? (
              <span className="ml-2 font-mono text-base tabular-nums">{activeItems[0].prescriptionFolio}</span>
            ) : null}
          </DialogTitle>
          <DialogDescription>
            Busca en el catálogo institucional. Cada medicamento lleva vía,
            frecuencia y duración.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {isLoadingItems ? (
            <p className="text-sm text-txt-muted">Cargando...</p>
          ) : activeItems.length > 0 ? (
            <PrescriptionItemsList visitId={visitId} items={activeItems} />
          ) : (
            <p className="text-sm text-txt-muted">Sin medicamentos todavía.</p>
          )}

          {allergyWarning ? (
            <div className="space-y-2 rounded-lg border border-status-critical/50 bg-status-critical/5 p-3">
              <p className="text-sm font-semibold text-status-critical">
                {allergyWarning.fromLegacy
                  ? `⚠️ Alergia del sistema anterior, sin confirmar: ${allergyWarning.substance}`
                  : `⚠️ Alergia registrada: ${allergyWarning.substance}`}
                {allergyWarning.severity ? ` (${SEVERITY_LABEL[allergyWarning.severity]})` : ""}
              </p>
              {allergyWarning.fromLegacy ? (
                <p className="text-xs text-txt-muted">
                  Viene de {allergyWarning.legacyOrigin}. Revisala en Historial → Datos del sistema anterior.
                </p>
              ) : null}
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
              className="space-y-4 border-t border-line-hairline pt-4"
            >
              <div className="space-y-2">
                {selectedMedication ? (
                  <>
                    <Label>Medicamento</Label>
                    <div className="flex items-start justify-between gap-3 rounded-lg border border-brand/40 bg-brand/5 p-3">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold break-words text-txt-body">
                            {selectedMedication.name}
                          </p>
                          <MedicationControlBadges
                            isControlled={selectedMedication.isControlled}
                            cuadroBasico={selectedMedication.cuadroBasico}
                          />
                        </div>
                        <p className="text-xs break-words text-txt-muted">
                          {[selectedMedication.genericName, selectedMedication.presentation, selectedMedication.code]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                        {selectedMedication.maxQuantity ? (
                          <p className="text-xs text-txt-muted">
                            Máximo {selectedMedication.maxQuantity} cajas por receta.
                          </p>
                        ) : null}
                      </div>
                      <Button type="button" variant="ghost" size="sm" onClick={() => selectMedication(null)}>
                        Cambiar
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    <Label htmlFor="medication-search">Buscar medicamento</Label>
                    <Input
                      id="medication-search"
                      value={search}
                      autoComplete="off"
                      placeholder="Nombre, genérico o clave"
                      onChange={(event) => setSearch(event.target.value)}
                    />
                    {debouncedSearch.length < MIN_SEARCH_LENGTH ? (
                      <p className="text-xs text-txt-muted">Escribe al menos 2 letras.</p>
                    ) : medicationSearch.isFetching ? (
                      <p className="text-xs text-txt-muted">Buscando...</p>
                    ) : medicationSearch.isError ? (
                      <p className="text-xs text-status-critical" role="alert">
                        No se pudo buscar en el catálogo.
                      </p>
                    ) : searchResults.length === 0 ? (
                      <p className="text-xs text-txt-muted">Sin coincidencias en el catálogo.</p>
                    ) : (
                      <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-line-hairline bg-paper p-1">
                        {searchResults.map((medication) => (
                          <button
                            key={medication.id}
                            type="button"
                            className="w-full rounded-md px-3 py-2 text-left transition hover:bg-subtle/40 focus-visible:bg-subtle/40 focus-visible:outline-none"
                            onClick={() => selectMedication(medication)}
                          >
                            <span className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-medium break-words text-txt-body">
                                {medication.name}
                              </span>
                              <MedicationControlBadges
                                isControlled={medication.isControlled}
                                cuadroBasico={medication.cuadroBasico}
                              />
                            </span>
                            <span className="block text-xs break-words text-txt-muted">
                              {[medication.genericName, medication.presentation, medication.code]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
                {medicationError ? (
                  <p className="text-sm text-status-critical" role="alert">
                    {medicationError}
                  </p>
                ) : null}
              </div>

              <PrescriptionItemFields form={form} maxQuantity={selectedMedication?.maxQuantity} />

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
