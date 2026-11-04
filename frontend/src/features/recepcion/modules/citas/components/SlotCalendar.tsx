import { useEffect, useState, type ReactNode } from "react";
import { DoorClosed, DoorOpen, Globe, Loader2, Plus, Stethoscope, X } from "lucide-react";
import type { AgendaSlot } from "@api/types/agenda.types";
import { useAgendaSemanal } from "@features/recepcion/modules/citas/queries/useAgendaSemanal";
import { addDays } from "@features/recepcion/modules/citas/utils/dates";
import { cn } from "@shared/utils/styling/cn";
import {
  CancelarCitaDialog,
  type CitaACancelar,
} from "@features/recepcion/modules/citas/components/CancelarCitaDialog";
import { CITA_ESTATUS_CANCELABLE } from "@features/recepcion/modules/citas/domain/citaEstatus.errors";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const DAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const GRID_COLS  = "56px repeat(7, minmax(0, 1fr))";

function formatDayDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("es-MX", {
    day: "2-digit", month: "short",
  });
}

function nowToday(): string {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-");
}

function isPastSlot(dateStr: string, hora: string, today: string, now: Date): boolean {
  if (dateStr < today) return true;
  if (dateStr === today) {
    const [h, m] = hora.split(":").map(Number);
    return h * 60 + m <= now.getHours() * 60 + now.getMinutes();
  }
  return false;
}

// "Libre" para recepción: disponible, vigente y no exclusivo del portal (canal="LINEA").
function esLibreRecepcion(fecha: string, slot: AgendaSlot, today: string, now: Date): boolean {
  return slot.disponible && slot.canal !== "LINEA" && !isPastSlot(fecha, slot.hora, today, now);
}

// ─── Agrupación visual por consultorio (carriles) ─────────────────────────────

interface Carril {
  key:     string;
  numero:  number | null;
  nombre:  string | null;
  horas:   string[];
  // Slot por "fecha|hora" dentro de este consultorio.
  slots:   Map<string, AgendaSlot>;
}

function agruparPorConsultorio(
  agenda: Record<string, AgendaSlot[]> | undefined,
  days: string[],
): Carril[] {
  const carriles = new Map<string, Carril>();
  for (const fecha of days) {
    for (const slot of agenda?.[fecha] ?? []) {
      const key = slot.consultorioId != null ? String(slot.consultorioId) : "sin-consultorio";
      let carril = carriles.get(key);
      if (!carril) {
        carril = { key, numero: slot.consultorioNumero, nombre: slot.consultorioNombre, horas: [], slots: new Map() };
        carriles.set(key, carril);
      }
      carril.slots.set(`${fecha}|${slot.hora}`, slot);
      if (!carril.horas.includes(slot.hora)) carril.horas.push(slot.hora);
    }
  }
  return Array.from(carriles.values())
    .map((c) => ({ ...c, horas: c.horas.sort() }))
    .sort((a, b) => (a.numero ?? Number.MAX_SAFE_INTEGER) - (b.numero ?? Number.MAX_SAFE_INTEGER));
}

function tituloCarril(carril: Carril): string {
  if (carril.numero != null) return `Consultorio ${carril.numero}`;
  return carril.nombre ?? "Sin consultorio asignado";
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface SlotCalendarProps {
  medicoId:      number;
  medicoNombre?: string;
  weekStart:     string;
  onSlotClick:   (fecha: string, slot: AgendaSlot) => void;
}

// ─── Subcomponente: celda de slot ─────────────────────────────────────────────

interface SlotCellProps {
  dateStr:         string;
  hora:            string;
  slot:            AgendaSlot | undefined;
  consultorio:     string;
  today:           string;
  now:             Date;
  isToday:         boolean;
  onClick:         (dateStr: string, slot: AgendaSlot) => void;
  onCancelarCita:  (cita: CitaACancelar) => void;
}

const CELL_BASE = "relative h-[68px] w-full overflow-hidden rounded-lg border border-l-4 px-2 py-1.5 flex flex-col justify-between text-left";

function SlotCell({ dateStr, hora, slot, consultorio, today, now, isToday, onClick, onCancelarCita }: SlotCellProps) {
  if (!slot) {
    return (
      <div
        className={cn(
          "h-[68px] rounded-lg border border-dashed border-line-hairline bg-subtle/10",
          isToday && "border-brand/20 bg-brand/[0.03]",
        )}
      />
    );
  }

  const esPasado     = isPastSlot(dateStr, slot.hora, today, now);
  const esOcupado    = !slot.disponible && !esPasado;
  // Slot disponible pero reservado exclusivamente para el portal de citas en
  // línea — no se puede agendar desde recepción.
  const esSoloPortal = slot.disponible && !esPasado && slot.canal === "LINEA";

  if (esPasado) {
    return (
      <div
        className={cn(CELL_BASE, "border-line-hairline border-l-line-struct bg-subtle/20 opacity-60")}
        title={`${hora} — Horario pasado · ${consultorio}`}
      >
        <p className="font-mono text-sm font-bold text-txt-hint line-through tabular-nums">{hora}</p>
        <p className="text-[10px] text-txt-hint">Pasado</p>
      </div>
    );
  }

  if (esOcupado) {
    // La cita ya reservada puede venir del portal de citas en línea
    // ("origenCanal" = "PORTAL") o haberse agendado directo en recepción —
    // se distingue con el mismo ícono que usa "Solo portal" para el slot
    // todavía libre, así el vocabulario visual es consistente antes y
    // después de reservarse.
    const esPortal = slot.cita?.origenCanal === "PORTAL";
    const esCancelable = !!slot.cita && CITA_ESTATUS_CANCELABLE.has(slot.cita.estatus);
    return (
      <div
        className={cn(
          CELL_BASE,
          "group/cell border-status-alert/40 border-l-status-alert bg-gradient-to-br from-status-alert/25 to-status-alert/10",
          isToday && "border-status-alert/60",
        )}
        title={`${hora} — Ocupado${slot.cita ? ` · Exp. ${slot.cita.noExp}` : ""}${esPortal ? " · Reservada en línea" : ""} · ${consultorio}`}
      >
        {esCancelable && slot.cita && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onCancelarCita({
                id:    slot.cita!.id,
                folio: slot.cita!.folio,
                noExp: slot.cita!.noExp,
                fecha: dateStr,
                hora,
              });
            }}
            title="Cancelar cita"
            aria-label="Cancelar cita"
            className="absolute right-1 top-1 flex size-5 items-center justify-center rounded-full bg-paper text-status-alert shadow-sm opacity-0 transition-opacity hover:bg-status-critical hover:text-txt-inverse focus-visible:opacity-100 group-hover/cell:opacity-100"
          >
            <X className="size-3" />
          </button>
        )}
        <div className="flex items-center gap-1 pr-5">
          <span className="font-mono text-sm font-bold text-txt-body tabular-nums">{hora}</span>
          {esPortal && <Globe className="size-3 shrink-0 text-status-info" />}
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase leading-tight tracking-wide text-status-alert">Agendado</p>
          {slot.cita?.noExp && (
            <p className="truncate font-mono text-[10px] text-txt-muted">Exp. {slot.cita.noExp}</p>
          )}
        </div>
      </div>
    );
  }

  if (esSoloPortal) {
    return (
      <div
        className={cn(
          CELL_BASE,
          "border-status-info/40 border-l-status-info bg-gradient-to-br from-status-info/20 to-status-info/5",
          isToday && "border-status-info/60",
        )}
        title={`${hora} — Reservado para citas en línea, no agendable desde recepción · ${consultorio}`}
      >
        <span className="font-mono text-sm font-bold text-txt-body tabular-nums">{hora}</span>
        <div className="flex items-center gap-1 text-status-info">
          <Globe className="size-3 shrink-0" />
          <p className="text-[10px] font-bold uppercase leading-tight tracking-wide">Solo portal</p>
        </div>
      </div>
    );
  }

  // Libre
  return (
    <button
      type="button"
      onClick={() => onClick(dateStr, slot)}
      title={`${hora} — Disponible · ${slot.duracionMin} min · ${consultorio}`}
      className={cn(
        CELL_BASE,
        "group cursor-pointer border-status-stable/40 border-l-status-stable",
        "bg-gradient-to-br from-status-stable/20 to-status-stable/5",
        "transition-all duration-150 hover:-translate-y-0.5 hover:from-status-stable hover:to-status-stable hover:shadow-lg hover:shadow-status-stable/25",
        "active:translate-y-0 active:scale-[0.98]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-status-stable/50",
        isToday && "ring-1 ring-status-stable/40",
      )}
    >
      <span className="font-mono text-sm font-bold text-status-stable tabular-nums transition-colors group-hover:text-txt-inverse">
        {hora}
      </span>
      <div className="flex w-full items-end justify-between gap-1">
        <span className="text-[10px] font-medium text-txt-muted transition-colors group-hover:text-txt-inverse">
          {slot.duracionMin} min
        </span>
        <span className="flex items-center gap-0.5 rounded-full bg-txt-inverse px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-status-stable opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          <Plus className="size-2.5" /> Ficha
        </span>
      </div>
    </button>
  );
}

// ─── Subcomponentes del resumen ───────────────────────────────────────────────

// Va sobre la placa naranja del médico: fondo claro + punto de color del estado.
function StatTile({ value, label, tone }: { value: number; label: string; tone: "stable" | "alert" | "info" }) {
  return (
    <div className="flex min-w-[96px] flex-col rounded-xl bg-paper/95 px-3 py-1.5 shadow-sm">
      <span className="flex items-center gap-1.5">
        <span
          className={cn(
            "size-2 rounded-full",
            tone === "stable" && "bg-status-stable",
            tone === "alert"  && "bg-status-alert",
            tone === "info"   && "bg-status-info",
          )}
        />
        <span
          className={cn(
            "text-xl font-extrabold leading-tight tabular-nums",
            tone === "stable" && "text-status-stable",
            tone === "alert"  && "text-status-alert",
            tone === "info"   && "text-status-info",
          )}
        >
          {value}
        </span>
      </span>
      <span className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">{label}</span>
    </div>
  );
}

function LegendItem({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn("inline-block h-3 w-4 rounded-sm border border-l-[3px]", className)} />
      {children}
    </span>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export function SlotCalendar({ medicoId, medicoNombre, weekStart, onSlotClick }: SlotCalendarProps) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const [citaACancelar, setCitaACancelar] = useState<CitaACancelar | null>(null);

  const today   = nowToday();
  const weekEnd = addDays(weekStart, 6);
  const days    = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  const { data, isFetching, isError } = useAgendaSemanal(medicoId, weekStart, weekEnd);

  const carriles = agruparPorConsultorio(data?.agenda, days);

  const libresPorDia = (d: string) =>
    (data?.agenda[d] ?? []).filter((s) => esLibreRecepcion(d, s, today, now)).length;

  // Conteos para el resumen
  const totalLibres  = days.reduce((acc, d) => acc + libresPorDia(d), 0);
  const totalOcupados = days.reduce((acc, d) =>
    acc + (data?.agenda[d] ?? []).filter((s) => !s.disponible && !isPastSlot(d, s.hora, today, now)).length, 0);
  const totalSoloPortal = days.reduce((acc, d) =>
    acc + (data?.agenda[d] ?? []).filter((s) =>
      s.disponible && s.canal === "LINEA" && !isPastSlot(d, s.hora, today, now)
    ).length, 0);

  const totalVigentes = totalLibres + totalOcupados + totalSoloPortal;
  const ocupacionPct  = totalVigentes > 0 ? Math.round((totalOcupados / totalVigentes) * 100) : 0;

  if (isError) {
    return (
      <p className="py-8 text-center text-sm text-status-critical">
        No se pudo cargar la disponibilidad. Intenta de nuevo.
      </p>
    );
  }

  return (
    <div className="relative space-y-4">

      {/* ── Header: placa del médico + resumen ──────────────────────── */}
      <div className="flex flex-wrap items-stretch justify-between gap-3 rounded-2xl bg-gradient-to-r from-brand to-brand-hover p-4 text-txt-inverse shadow-md shadow-brand/20">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-txt-inverse/20 ring-1 ring-txt-inverse/30">
            <Stethoscope className="size-6" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-wider opacity-80">Agenda semanal</p>
            <p className="truncate text-lg font-bold">{medicoNombre ?? "Médico"}</p>
            {data && !isFetching && totalVigentes > 0 && (
              <div className="mt-1 flex items-center gap-2">
                <div className="h-2 w-36 overflow-hidden rounded-full bg-txt-inverse/25">
                  <div className="h-full rounded-full bg-txt-inverse" style={{ width: `${ocupacionPct}%` }} />
                </div>
                <span className="text-[11px] font-semibold tabular-nums">{ocupacionPct}% ocupado</span>
              </div>
            )}
          </div>
        </div>

        {data && !isFetching && (
          <div className="flex flex-wrap items-center gap-2">
            <StatTile value={totalLibres}   label="Disponibles" tone="stable" />
            <StatTile value={totalOcupados} label="Agendados"   tone="alert" />
            {totalSoloPortal > 0 && <StatTile value={totalSoloPortal} label="Solo portal" tone="info" />}
          </div>
        )}
      </div>

      {/* ── Leyenda ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-txt-muted">
        <LegendItem className="border-status-stable/40 border-l-status-stable bg-status-stable/20">
          <span className="font-medium text-txt-body">Disponible</span> — clic para generar ficha
        </LegendItem>
        <LegendItem className="border-status-alert/40 border-l-status-alert bg-status-alert/25">
          <span className="font-medium text-txt-body">Agendado</span>
        </LegendItem>
        <LegendItem className="border-status-info/40 border-l-status-info bg-status-info/20">
          <span className="font-medium text-txt-body">Solo portal</span> — no agendable aquí
        </LegendItem>
        <LegendItem className="border-line-hairline border-l-line-struct bg-subtle/20">
          Pasado / sin horario
        </LegendItem>
      </div>

      {/* Overlay de carga */}
      {isFetching && data ? (
        <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl bg-paper/70 backdrop-blur-[1px]">
          <div className="flex items-center gap-2 rounded-full border border-line-struct bg-paper px-3 py-1.5 text-sm text-txt-muted shadow-sm">
            <Loader2 className="size-4 animate-spin" /> Actualizando...
          </div>
        </div>
      ) : null}

      {/* ── Grilla ──────────────────────────────────────────────────── */}
      <div className="overflow-x-auto">
        <div className="min-w-[680px] space-y-3">

          {/* Cabecera de días (una sola vez, compartida por todos los carriles) */}
          <div className="sticky top-0 z-10 grid gap-1.5 bg-paper/90 py-1 backdrop-blur-sm" style={{ gridTemplateColumns: GRID_COLS }}>
            <div />
            {days.map((dateStr, i) => {
              const isToday   = dateStr === today;
              const isPastDay = dateStr < today;
              const libres    = libresPorDia(dateStr);
              return (
                <div
                  key={dateStr}
                  className={cn(
                    "rounded-lg border border-t-4 px-1 py-2 text-center",
                    isToday
                      ? "border-brand bg-gradient-to-b from-brand to-brand-hover text-txt-inverse shadow-md shadow-brand/25"
                      : isPastDay
                      ? "border-line-hairline bg-subtle/30"
                      : libres > 0
                      ? "border-line-struct border-t-status-stable bg-paper"
                      : "border-line-struct border-t-line-struct bg-paper",
                  )}
                >
                  <p className={cn(
                    "text-[11px] font-bold uppercase tracking-wider",
                    isToday ? "text-txt-inverse" : isPastDay ? "text-txt-hint" : "text-txt-muted",
                  )}>
                    {DAY_LABELS[i]}{isToday ? " · hoy" : ""}
                  </p>
                  <p className={cn(
                    "font-mono text-sm font-semibold",
                    isToday ? "text-txt-inverse" : isPastDay ? "text-txt-hint" : "text-txt-body",
                  )}>
                    {formatDayDate(dateStr)}
                  </p>
                  {data && !isPastDay && (
                    <span className={cn(
                      "mt-1 inline-block rounded-full px-1.5 py-px text-[9px] font-semibold tabular-nums",
                      isToday
                        ? "bg-txt-inverse/20 text-txt-inverse"
                        : libres > 0
                        ? "bg-status-stable/15 text-status-stable"
                        : "bg-subtle text-txt-hint",
                    )}>
                      {libres > 0 ? `${libres} libres` : "Sin cupo"}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Skeleton primera carga */}
          {!data && isFetching ? (
            <div className="space-y-1.5 rounded-xl border border-line-struct p-2">
              <div className="h-10 animate-pulse rounded-lg bg-subtle/60" />
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="grid gap-1.5" style={{ gridTemplateColumns: GRID_COLS }}>
                  <div />
                  {Array.from({ length: 7 }).map((_, j) => (
                    <div key={j} className="h-[68px] animate-pulse rounded-lg bg-subtle/40" />
                  ))}
                </div>
              ))}
            </div>

          ) : carriles.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-16 text-center">
              <DoorClosed className="size-10 text-txt-hint" />
              <p className="text-sm font-medium text-txt-muted">Sin horarios configurados para esta semana.</p>
              <p className="text-xs text-txt-hint">Verificá la agenda del médico en configuración.</p>
            </div>

          ) : (
            carriles.map((carril) => {
              const titulo = tituloCarril(carril);
              const libresCarril = Array.from(carril.slots.entries()).filter(([k, s]) =>
                esLibreRecepcion(k.split("|")[0], s, today, now)
              ).length;
              return (
                <section
                  key={carril.key}
                  aria-label={titulo}
                  className="overflow-hidden rounded-xl border border-line-struct bg-subtle/10"
                >
                  {/* Cabecera del carril: la "puerta" del consultorio */}
                  <div className="flex items-center justify-between gap-3 border-b border-line-struct bg-paper px-3 py-2">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand">
                        <DoorOpen className="size-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-txt-body">{titulo}</p>
                        {carril.numero != null && carril.nombre && (
                          <p className="truncate text-[11px] text-txt-muted">{carril.nombre}</p>
                        )}
                      </div>
                    </div>
                    <span
                      className={cn(
                        "shrink-0 rounded-full px-2.5 py-1 text-xs font-bold tabular-nums",
                        libresCarril > 0
                          ? "bg-status-stable text-txt-inverse"
                          : "bg-subtle text-txt-muted",
                      )}
                    >
                      {libresCarril > 0 ? `${libresCarril} libres` : "Sin cupo"}
                    </span>
                  </div>

                  <div className="space-y-1.5 p-2">
                    {carril.horas.map((hora) => (
                      <div key={hora} className="grid gap-1.5" style={{ gridTemplateColumns: GRID_COLS }}>
                        {/* Eje de horas tipo línea de tiempo */}
                        <div className="relative flex items-start justify-end pr-3 pt-2">
                          <span className="font-mono text-[11px] font-semibold text-txt-hint tabular-nums">{hora}</span>
                          <span className="absolute right-0 top-[13px] size-1.5 rounded-full bg-line-struct" />
                        </div>

                        {days.map((dateStr) => (
                          <SlotCell
                            key={dateStr}
                            dateStr={dateStr}
                            hora={hora}
                            slot={carril.slots.get(`${dateStr}|${hora}`)}
                            consultorio={titulo}
                            today={today}
                            now={now}
                            isToday={dateStr === today}
                            onClick={onSlotClick}
                            onCancelarCita={setCitaACancelar}
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                </section>
              );
            })
          )}

        </div>
      </div>

      <CancelarCitaDialog
        cita={citaACancelar}
        onOpenChange={(open) => {
          if (!open) setCitaACancelar(null);
        }}
      />
    </div>
  );
}
