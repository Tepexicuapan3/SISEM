import { AlertTriangle } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { PrescriptionItemsList } from "@features/consulta-medica/modules/atencion/components/PrescriptionItemsList";
import { activePrescriptionItems } from "@features/consulta-medica/modules/atencion/domain/prescription-items";

interface PrescriptionSummaryProps {
  visitId: number;
  disabled?: boolean;
}

const plural = (count: number, singular: string, pluralForm: string) =>
  `${count} ${count === 1 ? singular : pluralForm}`;

/**
 * Medicamentos de la receta dentro de la consulta: el medico ve lo que lleva
 * recetado y cuantos piden autorizacion antes de cerrar.
 */
export function PrescriptionSummary({ visitId, disabled = false }: PrescriptionSummaryProps) {
  const { data, isLoading } = usePrescriptionItems(visitId);
  const items = activePrescriptionItems(data?.items);
  const needAuthorization = items.filter((item) => item.requiresAuthorization).length;

  if (isLoading) {
    return <p className="text-sm text-txt-muted">Cargando medicamentos...</p>;
  }

  if (items.length === 0) {
    return (
      <div className="space-y-1 rounded-lg border border-dashed border-line-struct p-3">
        <p className="text-sm text-txt-body">Sin medicamentos todavía.</p>
        <p className="text-xs text-txt-muted">
          Guarda el diagnóstico antes de agregar medicamentos.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{plural(items.length, "medicamento", "medicamentos")}</Badge>
        {needAuthorization > 0 ? (
          <Badge variant="alert" className="gap-1">
            <AlertTriangle className="size-3" />
            {plural(needAuthorization, "requiere autorización", "requieren autorización")}
          </Badge>
        ) : null}
      </div>
      <PrescriptionItemsList visitId={visitId} items={items} disabled={disabled} />
      {needAuthorization > 0 ? (
        <p className="text-xs text-txt-muted">
          Al finalizar, la receta queda pendiente hasta que la autorice otro usuario; después se imprime.
        </p>
      ) : null}
    </div>
  );
}
