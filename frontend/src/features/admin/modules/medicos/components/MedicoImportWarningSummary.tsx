import { TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Badge } from "@shared/ui/badge";
import type { MedicoImportWarningSummaryItem } from "@api/types/medicos.types";

// Filas listadas por tipo antes de resumir con "y N más": con miles de
// médicos la lista completa no aporta y rompe el layout.
const MAX_ROWS_LISTED = 25;

const formatRows = (rows: number[]) => {
  const listed = rows.slice(0, MAX_ROWS_LISTED).join(", ");
  const remaining = rows.length - MAX_ROWS_LISTED;
  return remaining > 0 ? `${listed} y ${remaining} más` : listed;
};

interface MedicoImportWarningSummaryProps {
  totalWarnings: number;
  summary: MedicoImportWarningSummaryItem[];
}

/**
 * Resumen general de advertencias del import de médicos, agrupado por tipo.
 * Reemplaza el detalle por fila en la tabla: cada tipo muestra cuántas filas
 * afecta y cuáles son. Las advertencias no bloquean la importación.
 */
export function MedicoImportWarningSummary({
  totalWarnings,
  summary,
}: MedicoImportWarningSummaryProps) {
  if (totalWarnings === 0 || summary.length === 0) return null;

  return (
    <Alert variant="warning">
      <TriangleAlert className="size-4" />
      <AlertTitle>
        {totalWarnings} fila{totalWarnings !== 1 ? "s" : ""} con advertencia
      </AlertTitle>
      <AlertDescription>
        <p>
          Las advertencias no bloquean la importación. Resumen por tipo:
        </p>
        <ul className="mt-3 space-y-3" aria-label="Resumen de advertencias">
          {summary.map((item) => (
            <li key={item.code} className="space-y-1">
              <div className="flex items-start gap-2">
                <Badge variant="alert" className="shrink-0 tabular-nums">
                  {item.count}
                </Badge>
                <span className="text-txt-body">{item.description}</span>
              </div>
              <p className="pl-1 text-xs text-txt-muted">
                Fila{item.rows.length !== 1 ? "s" : ""}: {formatRows(item.rows)}
              </p>
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
