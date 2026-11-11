import { useRef, type KeyboardEvent } from "react";
import { CalendarClock, CalendarDays, ClipboardList, List, type LucideIcon } from "lucide-react";

export type AgendaView = "bandeja" | "proximas" | "disponibilidad" | "historial";

interface TabDef {
  id:    AgendaView;
  label: string;
  hint:  string;
  icon:  LucideIcon;
}

const TABS: TabDef[] = [
  { id: "bandeja",        label: "Bandeja",        hint: "Pacientes de hoy",      icon: List },
  { id: "proximas",       label: "Próximas citas", hint: "Citas ya agendadas",    icon: CalendarClock },
  { id: "disponibilidad", label: "Disponibilidad", hint: "Buscar horario libre",  icon: CalendarDays },
  { id: "historial",      label: "Historial",      hint: "Por expediente",        icon: ClipboardList },
];

interface Props {
  view:          AgendaView;
  onChange:      (view: AgendaView) => void;
  canReadCitas:  boolean;
  /** Visitas abiertas de hoy; sin valor no se muestra el contador. */
  bandejaCount?: number;
}

/**
 * Pestañas de la agenda: tarjetas grandes con una pista de para qué sirve
 * cada vista. Flechas izquierda/derecha cambian de pestaña (patrón tablist).
 */
export function AgendaTabs({ view, onChange, canReadCitas, bandejaCount }: Props) {
  const tabs = TABS.filter((t) => t.id !== "proximas" || canReadCitas);
  const refs = useRef<Partial<Record<AgendaView, HTMLButtonElement | null>>>({});

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const index = tabs.findIndex((t) => t.id === view);
    const step = event.key === "ArrowRight" ? 1 : -1;
    const next = tabs[(index + step + tabs.length) % tabs.length];
    onChange(next.id);
    refs.current[next.id]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label="Vistas de la agenda"
      onKeyDown={onKeyDown}
      className="grid grid-cols-2 gap-2 rounded-xl border border-line-struct bg-subtle/20 p-1.5 md:grid-cols-4"
    >
      {tabs.map((tab) => {
        const active = tab.id === view;
        const Icon = tab.icon;
        return (
          <button
            key={tab.id}
            ref={(el) => { refs.current[tab.id] = el; }}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={[
              "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              active
                ? "bg-paper shadow-sm ring-1 ring-primary/40"
                : "hover:bg-paper/70 active:scale-[0.98]",
            ].join(" ")}
          >
            <span
              className={[
                "flex size-9 shrink-0 items-center justify-center rounded-lg transition-colors",
                active
                  ? "bg-primary text-white"
                  : "bg-subtle text-txt-muted group-hover:text-primary",
              ].join(" ")}
            >
              <Icon className="size-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span
                className={[
                  "flex items-center gap-1.5 text-sm font-semibold",
                  active ? "text-txt-body" : "text-txt-muted group-hover:text-txt-body",
                ].join(" ")}
              >
                {tab.label}
                {tab.id === "bandeja" && bandejaCount !== undefined ? (
                  <span
                    className={[
                      "rounded-full px-1.5 text-[10px] font-bold tabular-nums",
                      active ? "bg-primary text-white" : "bg-subtle text-txt-muted",
                    ].join(" ")}
                  >
                    {bandejaCount}
                  </span>
                ) : null}
              </span>
              <span className="block truncate text-[11px] text-txt-muted">{tab.hint}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
