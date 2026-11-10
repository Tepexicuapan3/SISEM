import { useState } from "react";
import { ChevronRight, Loader2 } from "lucide-react";
import type { CanalMovimiento, CitaHistorialItem } from "@api/types";
import { useCitaHistorial } from "@features/recepcion/modules/citas/queries/useCitaHistorial";
import { ESTATUS_LABEL } from "../pages/RecepcionAgendaPage.helpers";

const CANAL_LABEL: Record<CanalMovimiento, string> = {
  RECEPCION: "Recepción",
  MEDICO:    "Médico",
  PORTAL:    "Portal",
  SISTEMA:   "Sistema",
};

/** Quién y desde dónde; los movimientos anteriores al canal no lo tienen. */
const autor = (entry: CitaHistorialItem): string => {
  const canal = entry.canal ? CANAL_LABEL[entry.canal] : null;
  if (entry.changedByNombre) return canal ? `${entry.changedByNombre} · ${canal}` : entry.changedByNombre;
  return canal ?? "Portal o automático";
};

const formatMomento = (iso: string): string =>
  new Date(iso).toLocaleString("es-MX", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "America/Mexico_City",
  });

/**
 * Bitácora NOM-024 de la cita: del alta a cada cambio de estatus, con quién
 * lo hizo. Se pide al abrirla. Sin usuario es el paciente desde el portal o
 * una tarea automática (no asistió, fichas automáticas).
 */
export function CitaMovimientos({ citaId }: { citaId: number }) {
  const [expanded, setExpanded] = useState(false);
  const { data: log, isLoading, isError } = useCitaHistorial(citaId, expanded);

  return (
    <div className="px-5 py-2.5 border-t border-line-struct/40 bg-subtle/10">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
      >
        <ChevronRight className={`size-3 transition-transform ${expanded ? "rotate-90" : ""}`} />
        {expanded ? "Ocultar movimientos" : "Ver movimientos — auditoría NOM-024 §6"}
      </button>

      {expanded ? (
        <div className="mt-3">
          {isLoading ? (
            <div className="flex items-center gap-2 text-xs text-txt-muted py-1">
              <Loader2 className="size-3 animate-spin" /> Cargando historial de movimientos...
            </div>
          ) : isError ? (
            <p className="text-xs text-status-critical py-1">No se pudieron cargar los movimientos.</p>
          ) : log && log.length > 0 ? (
            <ol className="space-y-0 pl-1 border-l-2 border-line-struct/40">
              {log.map((entry) => (
                <li key={entry.id} className="relative flex items-start gap-3 py-2 pl-3">
                  <div className="absolute -left-[5px] top-3 size-2 rounded-full bg-primary/50 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1 text-xs">
                      {entry.fromStatus ? (
                        <>
                          <span className="text-txt-muted">{ESTATUS_LABEL[entry.fromStatus]}</span>
                          <span className="text-txt-muted">→</span>
                        </>
                      ) : null}
                      <span className="font-semibold text-txt-body">{ESTATUS_LABEL[entry.toStatus]}</span>
                    </div>
                    <p className="text-[10px] text-txt-muted mt-0.5">
                      {formatMomento(entry.changedAt)} · {autor(entry)}
                    </p>
                    {entry.notes ? (
                      <p className="text-[10px] italic text-txt-muted/70 mt-0.5">{entry.notes}</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-xs text-txt-muted py-1 italic">Sin movimientos registrados.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
