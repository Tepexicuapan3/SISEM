import { toast } from "sonner";
import { X } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { useCancelPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem";
import { MedicationControlBadges } from "@features/consulta-medica/modules/atencion/components/MedicationControlBadges";
import { resolvePrescriptionItemError } from "@features/consulta-medica/modules/atencion/domain/prescription-item-errors";
import { administrationText } from "@features/consulta-medica/modules/atencion/domain/prescription-items";
import type { PrescriptionItem } from "@api/types";

interface PrescriptionItemsListProps {
  visitId: number;
  items: PrescriptionItem[];
  disabled?: boolean;
}

/** Renglones de la receta: medicamento, como se toma, cantidad y si pide autorizacion. */
export function PrescriptionItemsList({ visitId, items, disabled = false }: PrescriptionItemsListProps) {
  const cancelItem = useCancelPrescriptionItem();

  const handleCancel = async (itemId: number) => {
    try {
      await cancelItem.mutateAsync({ visitId, itemId });
      toast.success("Medicamento quitado de la receta");
    } catch (error) {
      toast.error("No se pudo quitar el medicamento", { description: resolvePrescriptionItemError(error) });
    }
  };

  return (
    <ol className="divide-y divide-line-hairline rounded-lg border border-line-hairline bg-paper">
      {items.map((item, index) => (
        <li key={item.id} className="flex items-start gap-3 p-3">
          <span className="mt-0.5 w-5 shrink-0 text-right font-mono text-xs text-txt-muted tabular-nums">
            {index + 1}
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold break-words text-txt-body">{item.medicationName}</p>
              <MedicationControlBadges isControlled={item.isControlled} cuadroBasico={item.cuadroBasico} />
              {item.dispensedQuantity > 0 ? (
                <Badge variant="info">
                  {item.dispensationStatus === "dispensado"
                    ? "Surtido"
                    : `Surtido ${item.dispensedQuantity} de ${item.quantity}`}
                </Badge>
              ) : null}
            </div>
            {item.genericName || item.presentation ? (
              <p className="text-xs break-words text-txt-muted">
                {[item.genericName, item.presentation].filter(Boolean).join(" · ")}
              </p>
            ) : null}
            {administrationText(item) ? (
              <p className="text-sm leading-relaxed break-words text-txt-body">{administrationText(item)}</p>
            ) : null}
            <p className="text-sm leading-relaxed break-words whitespace-pre-wrap text-txt-muted">
              {item.indications}
            </p>
          </div>
          <span className="shrink-0 pt-0.5 text-sm text-txt-body tabular-nums">
            {item.quantity} {item.quantity === 1 ? "caja" : "cajas"}
          </span>
          {/* Candado de receta (5.3): lo surtido ya no se quita. */}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={item.canCancel ? "Quitar de la receta" : "Ya surtido: no se puede quitar"}
            title={item.canCancel ? undefined : "Farmacia ya lo surtió: no se puede quitar"}
            disabled={disabled || cancelItem.isPending || !item.canCancel}
            onClick={() => void handleCancel(item.id)}
          >
            <X className="size-4" />
          </Button>
        </li>
      ))}
    </ol>
  );
}
