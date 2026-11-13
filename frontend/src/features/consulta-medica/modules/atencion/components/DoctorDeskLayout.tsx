import { useState, type ReactNode } from "react";
import { cn } from "@shared/utils/styling/cn";

type DeskPane = "cola" | "consulta" | "atendidas";

const PANES: { value: DeskPane; label: string }[] = [
  { value: "cola", label: "Por atender" },
  { value: "consulta", label: "Consulta" },
  { value: "atendidas", label: "Atendidas hoy" },
];

interface DoctorDeskLayoutProps {
  queue:                  ReactNode;
  consultation:           ReactNode;
  attended:               ReactNode;
  hasOpenConsultation:    boolean;
}

/**
 * Mi consultorio (PROPUESTA): cola a la izquierda, consulta al centro y
 * atendidas hoy a la derecha, todo a la vista y sin ventanas encima.
 * En pantallas angostas las tres columnas pasan a pestañas.
 * Montarlo con `key` por paciente: abre en "Consulta" si hay uno abierto.
 */
export function DoctorDeskLayout({ queue, consultation, attended, hasOpenConsultation }: DoctorDeskLayoutProps) {
  const [pane, setPane] = useState<DeskPane>(hasOpenConsultation ? "consulta" : "cola");

  const column = (value: DeskPane) => cn(pane === value ? "block" : "hidden", "min-w-0 xl:block");

  return (
    <div className="space-y-3" data-testid="doctor-desk">
      <div role="tablist" aria-label="Mi consultorio" className="flex gap-1 rounded-xl border border-line-struct bg-subtle/20 p-1 xl:hidden">
        {PANES.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={pane === value}
            onClick={() => setPane(value)}
            className={cn(
              "flex-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              pane === value ? "bg-paper text-txt-body shadow-sm" : "text-txt-muted hover:text-txt-body",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[16rem_minmax(0,1fr)_22rem]">
        <aside aria-labelledby="desk-queue-title" className={cn(column("cola"), "xl:sticky xl:top-4")}>
          <h2 id="desk-queue-title" className="mb-2 text-sm font-semibold text-txt-body">Por atender</h2>
          {queue}
        </aside>
        <div className={column("consulta")}>{consultation}</div>
        <aside className={cn(column("atendidas"), "xl:sticky xl:top-4")}>{attended}</aside>
      </div>
    </div>
  );
}
