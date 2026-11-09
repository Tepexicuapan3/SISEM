import { useState } from "react";
import { useWatch, type UseFormReturn } from "react-hook-form";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, Info, X } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Calendar } from "@shared/ui/calendar";
import { cn } from "@shared/utils/styling/cn";
import { visitsAPI } from "@api/resources/visits.api";
import type {
  SaveDiagnosisFormInput,
  SaveDiagnosisFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";
import {
  FOLLOW_UP_SHORTCUTS,
  followUpMonthRange,
  groupSlotsByShift,
  minFollowUpDate,
  shortcutStartDate,
  type FollowUpShortcut,
} from "@features/consulta-medica/modules/atencion/domain/consultation-morbidity";

const toDateObj = (iso: string): Date => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
};

const toIso = (date: Date): string =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

const formatLongDate = (iso: string): string =>
  toDateObj(iso).toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" });

interface Props {
  visitId: number | null;
  diagnosisForm: UseFormReturn<SaveDiagnosisFormInput, unknown, SaveDiagnosisFormValues>;
  disabled: boolean;
}

/**
 * P-12: el médico saca la cita de seguimiento de SU agenda en pocos clics:
 * atajo (o día marcado en el calendario) -> horario. La cita se crea al
 * finalizar la consulta. Sin agenda, la fecha queda como indicación.
 */
export function FollowUpScheduler({ visitId, diagnosisForm, disabled }: Props) {
  const queryClient = useQueryClient();
  const followUpDate = useWatch({ control: diagnosisForm.control, name: "followUpDate" });
  const followUpSlotId = useWatch({ control: diagnosisForm.control, name: "followUpSlotId" });
  const followUpError = diagnosisForm.formState.errors.followUpDate?.message;
  const enabled = visitId !== null && !disabled;

  // Días con horarios libres del mes visible (y si el usuario tiene agenda).
  const [visibleMonth, setVisibleMonth] = useState(() => toDateObj(minFollowUpDate()));
  const monthRange = followUpMonthRange(visibleMonth);
  const { data: daysData, isFetching: loadingDays } = useQuery({
    queryKey: ["consulta-medica", "follow-up-days", visitId, monthRange?.desde, monthRange?.hasta],
    queryFn: () =>
      visitsAPI.getFollowUpDays(visitId as number, monthRange?.desde ?? "", monthRange?.hasta ?? ""),
    enabled: enabled && monthRange !== null,
    staleTime: 30 * 1000,
  });
  const hasAgenda = daysData?.hasAgenda ?? true;
  const days = daysData?.days ?? [];
  // Con lugar (verde) y llenos (rojo): igual que el calendario del portal de citas.
  const availableDays = new Set(days.filter((day) => day.libres > 0).map((day) => day.fecha));
  const fullDays = days.filter((day) => day.libres === 0).map((day) => toDateObj(day.fecha));

  // Horarios del día elegido, libres y ocupados.
  const fechaValida = !followUpError && /^\d{4}-\d{2}-\d{2}$/.test(followUpDate ?? "");
  const { data: slotsData, isFetching: loadingSlots } = useQuery({
    queryKey: ["consulta-medica", "follow-up-slots", visitId, followUpDate],
    queryFn: () => visitsAPI.getFollowUpSlots(visitId as number, followUpDate as string),
    enabled: enabled && hasAgenda && fechaValida,
    staleTime: 30 * 1000,
  });
  const slots = slotsData?.slots ?? [];
  const groups = groupSlotsByShift(slots);
  const showConsultorio = new Set(slots.map((slot) => slot.consultorioNombre)).size > 1;
  const freeSlots = slots.filter((slot) => slot.disponible);
  const selectedSlot = freeSlots.find((slot) => String(slot.slotId) === followUpSlotId);

  const [shortcutPending, setShortcutPending] = useState<string | null>(null);
  const [shortcutMessage, setShortcutMessage] = useState<string | null>(null);

  const selectDate = (iso: string) => {
    setShortcutMessage(null);
    diagnosisForm.setValue("followUpDate", iso, { shouldDirty: true, shouldValidate: true });
  };

  const applyShortcut = async (shortcut: FollowUpShortcut) => {
    if (visitId === null) return;
    const desde = shortcutStartDate(shortcut);
    setShortcutPending(shortcut.label);
    setShortcutMessage(null);
    try {
      const { fecha } = await queryClient.fetchQuery({
        queryKey: ["consulta-medica", "follow-up-next-day", visitId, desde],
        queryFn: () => visitsAPI.getFollowUpNextDay(visitId, desde),
        staleTime: 30 * 1000,
      });
      if (fecha) {
        selectDate(fecha);
        setVisibleMonth(toDateObj(fecha));
      } else {
        setShortcutMessage("No hay horarios libres a partir de esa fecha en tu agenda.");
      }
    } catch {
      setShortcutMessage("No se pudo consultar tu agenda. Intenta de nuevo.");
    } finally {
      setShortcutPending(null);
    }
  };

  const selectSlot = (slotId: number) => {
    diagnosisForm.setValue("followUpSlotId", String(slotId), { shouldDirty: true });
  };

  // Con agenda, solo se eligen días con lugar (cuando ya se cargó el mes).
  const disabledDays = disabled
    ? true
    : [
        { before: toDateObj(minFollowUpDate()) },
        ...(hasAgenda && daysData && !loadingDays
          ? [(date: Date) => !availableDays.has(toIso(date))]
          : []),
      ];

  return (
    <div className="space-y-3 rounded-lg border border-line-struct p-3">
      {!hasAgenda ? (
        <p className="flex items-start gap-2 rounded-md bg-subtle p-2 text-xs text-txt-body">
          <Info className="mt-0.5 size-4 shrink-0 text-status-info" aria-hidden="true" />
          Tu usuario no tiene agenda de médico, así que no hay horarios que ofrecer.
          Elige la fecha y la cita la agenda recepción.
        </p>
      ) : (
        <div className="space-y-1">
          <p className="text-xs font-medium text-txt-muted">Regresa en:</p>
          <div className="flex flex-wrap gap-2">
            {FOLLOW_UP_SHORTCUTS.map((shortcut) => (
              <Button
                key={shortcut.label}
                type="button"
                size="sm"
                variant="outline"
                disabled={disabled || shortcutPending !== null}
                onClick={() => void applyShortcut(shortcut)}
              >
                {shortcutPending === shortcut.label ? "Buscando..." : shortcut.label}
              </Button>
            ))}
          </div>
          {shortcutMessage ? (
            <p className="text-xs text-status-critical" role="status">
              {shortcutMessage}
            </p>
          ) : null}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-[minmax(0,18rem)_1fr]">
        <div className="rounded-xl border border-line-struct bg-paper p-2">
          <div className="mb-1 flex items-center justify-between gap-2 px-2 text-xs text-txt-muted">
            {hasAgenda ? (
              <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="flex items-center gap-1">
                  <span className="inline-block size-2.5 rounded-full bg-status-stable" />
                  Con lugar
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block size-2.5 rounded-full bg-status-critical" />
                  Lleno
                </span>
              </span>
            ) : (
              <span>Fecha de seguimiento</span>
            )}
            {loadingDays ? <span>Cargando...</span> : null}
          </div>
          <Calendar
            mode="single"
            selected={followUpDate ? toDateObj(followUpDate) : undefined}
            onSelect={(date) => {
              if (date) selectDate(toIso(date));
            }}
            month={visibleMonth}
            onMonthChange={setVisibleMonth}
            disabled={disabledDays}
            modifiers={{ disponible: [...availableDays].map(toDateObj), lleno: fullDays }}
            modifiersClassNames={{
              disponible:
                "after:absolute after:bottom-0.5 after:left-1/2 after:-translate-x-1/2 after:size-1 after:rounded-full after:bg-status-stable after:content-[''] relative",
              lleno:
                "after:absolute after:bottom-0.5 after:left-1/2 after:-translate-x-1/2 after:size-1 after:rounded-full after:bg-status-critical after:content-[''] relative",
            }}
            className="w-full"
          />
        </div>

        <div className="space-y-3">
          {!followUpDate ? (
            <p className="text-sm text-txt-muted">
              {hasAgenda
                ? "Elige un atajo o un día marcado en verde para ver tus horarios."
                : "Elige la fecha en el calendario."}
            </p>
          ) : (
            <p className="text-sm font-medium capitalize text-txt-body">{formatLongDate(followUpDate)}</p>
          )}

          {hasAgenda && followUpDate && fechaValida ? (
            loadingSlots ? (
              <p className="text-xs text-txt-muted">Buscando horarios...</p>
            ) : slots.length === 0 ? (
              <p className="text-xs text-txt-muted">
                No tienes horarios ese día. Elige un día marcado en verde.
              </p>
            ) : (
              <div className="space-y-2">
                <ul aria-label="Leyenda de horarios" className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-txt-muted">
                  <li className="flex items-center gap-1.5">
                    <span className="inline-block size-3 rounded-sm border border-status-stable bg-status-stable/15" />
                    Disponible
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="inline-block size-3 rounded-sm border border-status-critical/50 bg-status-critical/10" />
                    Ocupado
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="inline-block size-3 rounded-sm bg-status-stable" />
                    Elegido
                  </li>
                </ul>
                {freeSlots.length === 0 ? (
                  <p className="text-xs text-txt-muted">
                    Ese día ya está lleno. Elige un día marcado en verde.
                  </p>
                ) : null}
                {groups.map(({ shift, slots: shiftSlots }) => (
                  <div key={shift} className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-txt-muted">{shift}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {shiftSlots.map((slot) => {
                        const selected = slot.disponible && String(slot.slotId) === followUpSlotId;
                        return (
                          <button
                            key={slot.slotId}
                            type="button"
                            aria-pressed={slot.disponible ? selected : undefined}
                            aria-label={`${slot.hora} ${slot.disponible ? "disponible" : "ocupado"}`}
                            title={slot.disponible ? "Disponible" : "Ocupado"}
                            disabled={disabled || !slot.disponible}
                            onClick={() => selectSlot(slot.slotId)}
                            className={cn(
                              "flex min-w-16 flex-col items-center rounded-md border px-2 py-1 text-sm font-medium tabular-nums transition-colors",
                              "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-status-stable/40",
                              !slot.disponible &&
                                "cursor-not-allowed border-status-critical/50 bg-status-critical/10 text-status-critical line-through",
                              slot.disponible &&
                                !selected &&
                                "border-status-stable bg-status-stable/15 text-txt-body hover:bg-status-stable/25",
                              selected && "border-status-stable bg-status-stable text-txt-inverse",
                            )}
                          >
                            <span>{slot.hora}</span>
                            {showConsultorio && slot.consultorioNombre ? (
                              <span className="text-[10px] font-normal opacity-80">{slot.consultorioNombre}</span>
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : null}

          {selectedSlot && followUpDate ? (
            <div className="flex items-start justify-between gap-2 rounded-md border border-status-stable bg-status-stable/10 p-2 text-sm text-txt-body">
              <p className="flex items-start gap-2">
                <CalendarCheck className="mt-0.5 size-4 shrink-0 text-status-stable" aria-hidden="true" />
                <span>
                  <strong className="capitalize">{formatLongDate(followUpDate)}</strong> a las{" "}
                  <strong>{selectedSlot.hora}</strong>
                  {selectedSlot.consultorioNombre ? ` · ${selectedSlot.consultorioNombre}` : ""}.{" "}
                  La cita se agenda al finalizar la consulta.
                </span>
              </p>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label="Quitar horario"
                disabled={disabled}
                onClick={() => diagnosisForm.setValue("followUpSlotId", "", { shouldDirty: true })}
              >
                <X className="size-4" />
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
