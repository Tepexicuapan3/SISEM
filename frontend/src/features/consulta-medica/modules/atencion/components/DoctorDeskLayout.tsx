import { useState, type ReactNode } from "react";
import { Users } from "lucide-react";
import { cn } from "@shared/utils/styling/cn";
import { DeskPanel } from "./DeskPanel";

type DeskPane = "cola" | "consulta" | "atendidas";

interface DoctorDeskLayoutProps {
  queue:                  ReactNode;
  queueCount:             number;
  consultation:           ReactNode;
  attended:               ReactNode;
  attendedCount?:         number;
  hasOpenConsultation:    boolean;
}

/**
 * Mi consultorio (PROPUESTA): cola a la izquierda, consulta al centro y
 * atendidas hoy a la derecha, todo a la vista y sin ventanas encima.
 * En pantallas angostas las tres columnas pasan a pestañas.
 * Montarlo con `key` por paciente: abre en "Consulta" si hay uno abierto.
 */
export function DoctorDeskLayout({
  queue,
  queueCount,
  consultation,
  attended,
  attendedCount,
  hasOpenConsultation,
}: DoctorDeskLayoutProps) {
  const [pane, setPane] = useState<DeskPane>(hasOpenConsultation ? "consulta" : "cola");

  const panes: { value: DeskPane; label: string; count?: number }[] = [
    { value: "cola", label: "Por atender", count: queueCount },
    { value: "consulta", label: "Consulta" },
    { value: "atendidas", label: "Atendidas", count: attendedCount },
  ];
  const column = (value: DeskPane) => cn(pane === value ? "block" : "hidden", "min-w-0 xl:block");

  return (
    <div className="space-y-3" data-testid="doctor-desk">
      <div role="tablist" aria-label="Mi consultorio" className="flex gap-1 rounded-xl border border-line-struct bg-subtle/20 p-1 xl:hidden">
        {panes.map(({ value, label, count }) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={pane === value}
            onClick={() => setPane(value)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              pane === value ? "bg-paper text-txt-body shadow-sm" : "text-txt-muted hover:text-txt-body",
            )}
          >
            {label}
            {count ? (
              <span className="rounded-full bg-brand/10 px-1.5 font-mono text-[10px] text-brand tabular-nums">{count}</span>
            ) : null}
          </button>
        ))}
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_21rem]">
        <div className={cn(column("cola"), "xl:sticky xl:top-4")}>
          <DeskPanel icon={Users} title="Por atender" count={queueCount} hint="En consulta arriba; luego por hora de cita.">
            {queue}
          </DeskPanel>
        </div>
        <div className={column("consulta")}>{consultation}</div>
        <div className={cn(column("atendidas"), "xl:sticky xl:top-4")}>{attended}</div>
      </div>
    </div>
  );
}
