/**
 * Próximas citas de recepción: rangos rápidos y agrupación por día.
 */

const toIso = (date: Date): string =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

const addDays = (date: Date, days: number): Date =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);

export const PROXIMAS_RANGOS = [
  { value: "hoy", label: "Hoy" },
  { value: "manana", label: "Mañana" },
  { value: "7dias", label: "7 días" },
  { value: "30dias", label: "30 días" },
] as const;

export type ProximasRango = (typeof PROXIMAS_RANGOS)[number]["value"];

/** Rango de fechas (aaaa-mm-dd) que se pide al backend (máx. 31 días). */
export function rangoProximas(
  rango: ProximasRango,
  now: Date = new Date(),
): { fechaDesde: string; fechaHasta: string } {
  const hoy = toIso(now);
  switch (rango) {
    case "hoy":
      return { fechaDesde: hoy, fechaHasta: hoy };
    case "manana": {
      const manana = toIso(addDays(now, 1));
      return { fechaDesde: manana, fechaHasta: manana };
    }
    case "7dias":
      return { fechaDesde: hoy, fechaHasta: toIso(addDays(now, 7)) };
    case "30dias":
      return { fechaDesde: hoy, fechaHasta: toIso(addDays(now, 30)) };
  }
}

/** "Hoy · lunes, 9 de noviembre", "Mañana · …" o solo el día. */
function dayLabel(date: Date, now: Date): string {
  const text = date.toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" });
  const iso = toIso(date);
  if (iso === toIso(now)) return `Hoy · ${text}`;
  if (iso === toIso(addDays(now, 1))) return `Mañana · ${text}`;
  return text;
}

/** Agrupa por día local, respetando el orden (el backend ya ordena por hora). */
export function groupCitasByDay<T extends { fechaHora: string }>(
  items: T[],
  now: Date = new Date(),
): { fecha: string; label: string; items: T[] }[] {
  const groups: { fecha: string; label: string; items: T[] }[] = [];
  for (const item of items) {
    const date = new Date(item.fechaHora);
    const fecha = toIso(date);
    const last = groups[groups.length - 1];
    if (last?.fecha === fecha) {
      last.items.push(item);
    } else {
      groups.push({ fecha, label: dayLabel(date, now), items: [item] });
    }
  }
  return groups;
}
