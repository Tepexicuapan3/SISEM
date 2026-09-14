import { useState } from "react";
import { ChevronDown, ChevronUp, History } from "lucide-react";
import { useLegacyConsultationsHistory } from "@features/expedientes/queries/useLegacyConsultationsHistory";

interface Props {
  noExp: string;
  pkNum: number;
}

const formatFecha = (fecha: string) => {
  try {
    return new Date(fecha).toLocaleDateString("es-MX", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return fecha;
  }
};

/**
 * Notas del legado (previas a SIRES) -- archivo de solo lectura,
 * separado de las consultas reales de SIRES (ConsultationRepository /
 * usePatientConsultationsHistory). No tiene acciones (editar/cancelar/
 * aclarar) porque es un volcado histórico inmutable, no un registro
 * operativo.
 */
export const LegacyConsultationHistorySection = ({ noExp, pkNum }: Props) => {
  const [abierto, setAbierto] = useState(false);

  const { data, isLoading } = useLegacyConsultationsHistory(noExp, pkNum, abierto);

  return (
    <div className="mt-6 rounded-lg border border-line-struct">
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-subtle/40 transition-colors"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-txt-body">
          <History className="size-4 text-txt-muted" />
          Historial previo a SIRES (legado)
        </span>
        {abierto ? (
          <ChevronUp className="size-4 text-txt-muted" />
        ) : (
          <ChevronDown className="size-4 text-txt-muted" />
        )}
      </button>

      {abierto && (
        <div className="border-t border-line-struct p-4 space-y-3">
          {isLoading && (
            <p className="text-txt-muted text-sm text-center py-6">
              Cargando historial del legado...
            </p>
          )}

          {data && data.items.length === 0 && (
            <p className="text-txt-muted text-sm text-center py-6">
              No hay notas del legado para este paciente.
            </p>
          )}

          {data && data.items.length > 0 && (
            <>
              {data.totalCount > data.items.length && (
                <p className="text-xs text-txt-muted italic">
                  Mostrando las {data.items.length} más recientes de {data.totalCount} en total.
                </p>
              )}
              {data.items.map((nota) => (
                <div key={nota.id} className="p-3 bg-subtle rounded-md text-sm space-y-1">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-txt-body">
                      {formatFecha(nota.date)}
                      {nota.time ? ` — ${nota.time}` : ""}
                    </p>
                    <span className="font-mono text-xs text-txt-muted">{nota.legacyFolio}</span>
                  </div>
                  {nota.diagnosticImpression && (
                    <p className="text-txt-body">
                      <strong>Diagnóstico:</strong> {nota.diagnosticImpression}
                    </p>
                  )}
                  {nota.assessment && (
                    <p className="text-txt-muted">
                      <strong>Análisis:</strong> {nota.assessment}
                    </p>
                  )}
                  {nota.addendumLegacy && (
                    <p className="text-txt-muted italic">
                      <strong>Adenda del legado:</strong> {nota.addendumLegacy}
                    </p>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};
