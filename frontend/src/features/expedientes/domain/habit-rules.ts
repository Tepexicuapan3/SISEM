import type { HabitItem, HabitStatus } from "@api/types";

/** HABITO.estado (documento 5.2). */
export const HABIT_STATUS_OPTIONS: { value: HabitStatus; label: string }[] = [
  { value: "A", label: "Actual" },
  { value: "E", label: "Lo dejó" },
  { value: "N", label: "Lo niega" },
];

export const HABIT_STATUS_LABELS: Record<HabitStatus, string> = {
  A: "Actual",
  E: "Lo dejó",
  N: "Lo niega",
};

/** "" -> null; "2010" -> 2010; cualquier otra cosa -> NaN (para avisar). */
export function parseYear(text: string): number | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  return /^\d{4}$/.test(trimmed) ? Number(trimmed) : Number.NaN;
}

/** Mismas reglas que el backend (patient_record_usecase._validate_habit). */
export function habitError(
  values: Pick<HabitItem, "status" | "frequency" | "quantity" | "since" | "until">,
  thisYear: number = new Date().getFullYear(),
): string | null {
  for (const [label, year] of [["Desde", values.since], ["Hasta", values.until]] as const) {
    if (year === null) continue;
    if (Number.isNaN(year) || year < 1900 || year > thisYear) {
      return `${label}: escribe un año de 4 dígitos entre 1900 y ${thisYear}.`;
    }
  }
  if (values.status === "N" && (values.frequency || values.quantity || values.since || values.until)) {
    return "Si lo niega, no lleva frecuencia, cantidad ni años.";
  }
  if (values.until !== null && values.status !== "E") {
    return "El año en que lo dejó solo va con el estado «Lo dejó».";
  }
  if (values.since !== null && values.until !== null && values.until < values.since) {
    return "Lo dejó antes de empezar: revisa los años.";
  }
  return null;
}

/** "desde 2010 · hasta 2020" (o lo que haya). */
export function habitYears(item: Pick<HabitItem, "since" | "until">): string | null {
  const parts = [
    item.since !== null ? `desde ${item.since}` : null,
    item.until !== null ? `hasta ${item.until}` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}
