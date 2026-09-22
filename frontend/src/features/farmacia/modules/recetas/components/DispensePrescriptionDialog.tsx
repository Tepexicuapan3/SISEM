import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Checkbox } from "@shared/ui/checkbox";
import { Input } from "@shared/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@shared/ui/table";
import { ApiError } from "@api/utils/errors";
import type { DispensationPreviewItem } from "@api/types";
import { useDispensationPreview } from "../queries/useDispensacionQueries";
import { useDispensePrescription } from "../mutations/useDispensePrescription";
import { getDispensacionErrorMessage } from "../utils/dispensacion.feedback";

interface DispensePrescriptionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prescriptionId: number | null;
  idAlmacen: number | null;
}

type SelectionState = Record<number, { selected: boolean; quantity: number }>;

function buildInitialSelection(items: DispensationPreviewItem[]): SelectionState {
  const state: SelectionState = {};
  for (const item of items) {
    state[item.itemId] = {
      selected: item.hasMapping && item.pendingQuantity > 0,
      quantity: item.pendingQuantity,
    };
  }
  return state;
}

export function DispensePrescriptionDialog({
  open,
  onOpenChange,
  prescriptionId,
  idAlmacen,
}: DispensePrescriptionDialogProps) {
  const previewQuery = useDispensationPreview(prescriptionId, { enabled: open && prescriptionId !== null });
  const dispensePrescription = useDispensePrescription();

  const [selection, setSelection] = useState<SelectionState>({});

  useEffect(() => {
    if (previewQuery.data) {
      setSelection(buildInitialSelection(previewQuery.data.items));
    }
  }, [previewQuery.data]);

  const items = previewQuery.data?.items ?? [];
  const selectedItems = items.filter((item) => selection[item.itemId]?.selected);

  const handleConfirm = async () => {
    if (!prescriptionId || !idAlmacen || selectedItems.length === 0) return;

    try {
      await dispensePrescription.mutateAsync({
        prescriptionId,
        data: {
          idAlmacen,
          items: selectedItems.map((item) => ({
            itemId: item.itemId,
            quantity: selection[item.itemId]?.quantity ?? item.pendingQuantity,
          })),
        },
      });
      toast.success("Dispensacion registrada");
      onOpenChange(false);
    } catch (error) {
      const description = getDispensacionErrorMessage(error, "No se pudo dispensar la receta");
      if (error instanceof ApiError && error.code === "INSUFFICIENT_STOCK") {
        toast.warning(description);
      } else {
        toast.error("No se pudo dispensar la receta", { description });
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[85vw] lg:w-200">
        <DialogHeader>
          <DialogTitle>Dispensar receta</DialogTitle>
          <DialogDescription>
            Confirma la cantidad a dispensar de cada item. Los items sin insumo mapeado
            quedan bloqueados hasta que farmacia complete el mapeo.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[50vh] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Medicamento</TableHead>
                <TableHead className="text-center">Prescrito</TableHead>
                <TableHead className="text-center">Dispensado</TableHead>
                <TableHead className="text-center">Pendiente</TableHead>
                <TableHead className="text-center">A dispensar</TableHead>
                <TableHead className="text-center">Insumo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => {
                const rowSelection = selection[item.itemId];
                const disabled = !item.hasMapping || item.pendingQuantity <= 0;

                return (
                  <TableRow key={item.itemId}>
                    <TableCell>
                      <Checkbox
                        checked={rowSelection?.selected ?? false}
                        disabled={disabled}
                        onCheckedChange={(checked) =>
                          setSelection((prev) => ({
                            ...prev,
                            [item.itemId]: {
                              selected: Boolean(checked),
                              quantity: prev[item.itemId]?.quantity ?? item.pendingQuantity,
                            },
                          }))
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{item.medicationName}</div>
                      <div className="text-xs text-muted-foreground">{item.indications}</div>
                    </TableCell>
                    <TableCell className="text-center tabular-nums">{item.quantity}</TableCell>
                    <TableCell className="text-center tabular-nums">{item.dispensedQuantity}</TableCell>
                    <TableCell className="text-center tabular-nums">{item.pendingQuantity}</TableCell>
                    <TableCell className="text-center">
                      <Input
                        type="number"
                        min={1}
                        max={item.pendingQuantity}
                        className="w-20 mx-auto"
                        disabled={disabled || !(rowSelection?.selected ?? false)}
                        value={rowSelection?.quantity ?? item.pendingQuantity}
                        onChange={(e) =>
                          setSelection((prev) => ({
                            ...prev,
                            [item.itemId]: {
                              selected: prev[item.itemId]?.selected ?? false,
                              quantity: Number(e.target.value) || 1,
                            },
                          }))
                        }
                      />
                    </TableCell>
                    <TableCell className="text-center">
                      {item.hasMapping ? (
                        <span className="text-xs tabular-nums">{item.computedQuantity}</span>
                      ) : (
                        <Badge variant="critical" className="gap-1">
                          <AlertTriangle className="size-3" />
                          Sin insumo mapeado
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
          <Button
            type="button"
            onClick={() => { void handleConfirm(); }}
            disabled={dispensePrescription.isPending || selectedItems.length === 0 || !idAlmacen}
          >
            Dispensar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
