import type { ConsultationMorbidity, FollowUpSlot } from "@api/types";

/**
 * his_notas.sw_morbi (documento 5.3). Mismos codigos y textos que el legado
 * (body-consultadirectac.jsp): se refiere a la ENFERMEDAD, no a la visita.
 */
export const MORBIDITY_LABELS: Record<ConsultationMorbidity, string> = {
  "1": "Primera vez de la enfermedad",
  "2": "Subsecuente de la enfermedad",
};

/** Fecha local de hoy como aaaa-mm-dd (lo que devuelve un input type=date). */
export function todayIso(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Primer dia valido para el seguimiento: el siguiente a la consulta, y nunca
 * antes de mañana. Es la misma regla del backend (_validate_clinical_fields):
 * recepción puede registrar la ficha con una fecha posterior a hoy.
 */
export function minFollowUpDate(now: Date = new Date(), consultationDate?: string | null): string {
  const today = todayIso(now);
  const base = consultationDate && consultationDate > today ? consultationDate : today;
  const [y, m, d] = base.split("-").map(Number);
  return todayIso(new Date(y, m - 1, d + 1));
}

/**
 * Atajos de la cita de seguimiento: cada uno busca el primer día con
 * horarios libres a partir de "hoy + plazo" (como lo indica el médico).
 */
export const FOLLOW_UP_SHORTCUTS = [
  { label: "Próximo disponible", days: 0, months: 0 },
  { label: "1 semana", days: 7, months: 0 },
  { label: "2 semanas", days: 14, months: 0 },
  { label: "1 mes", days: 0, months: 1 },
  { label: "3 meses", days: 0, months: 3 },
] as const;

export type FollowUpShortcut = (typeof FOLLOW_UP_SHORTCUTS)[number];

/** Fecha desde la que se busca el atajo; nunca antes de mañana. */
export function shortcutStartDate(
  shortcut: FollowUpShortcut,
  now: Date = new Date(),
  consultationDate?: string | null,
): string {
  const target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + shortcut.days);
  if (shortcut.months) {
    const day = target.getDate();
    target.setDate(1);
    target.setMonth(target.getMonth() + shortcut.months);
    const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
    target.setDate(Math.min(day, lastDay));
  }
  const iso = todayIso(target);
  const min = minFollowUpDate(now, consultationDate);
  return iso < min ? min : iso;
}

export const SHIFTS = ["Mañana", "Tarde", "Noche"] as const;

/** Horarios agrupados por turno (mañana < 12:00 <= tarde < 18:00 <= noche). */
export function groupSlotsByShift(
  slots: FollowUpSlot[],
): { shift: (typeof SHIFTS)[number]; slots: FollowUpSlot[] }[] {
  const shiftOf = (hora: string) => (hora < "12:00" ? 0 : hora < "18:00" ? 1 : 2);
  return SHIFTS.map((shift, index) => ({
    shift,
    slots: slots.filter((slot) => shiftOf(slot.hora) === index),
  })).filter((group) => group.slots.length > 0);
}

/**
 * Rango de días que se consulta para marcar el calendario de seguimiento:
 * el mes visible, sin los días anteriores a mañana. null si ya pasó entero.
 */
export function followUpMonthRange(
  month: Date,
  now: Date = new Date(),
  consultationDate?: string | null,
): { desde: string; hasta: string } | null {
  const first = todayIso(new Date(month.getFullYear(), month.getMonth(), 1));
  const last = todayIso(new Date(month.getFullYear(), month.getMonth() + 1, 0));
  const min = minFollowUpDate(now, consultationDate);
  if (last < min) return null;
  return { desde: first < min ? min : first, hasta: last };
}

/**
 * Regla del legado: si el medico marca "cita", la fecha es obligatoria.
 * Mejora: tiene que ser posterior a hoy. null si esta bien.
 */
export function followUpError(
  enabled: boolean,
  date: string,
  now: Date = new Date(),
  consultationDate?: string | null,
): string | null {
  if (!enabled) return null;
  if (!date) return "Indica la fecha de seguimiento.";
  if (date < minFollowUpDate(now, consultationDate)) {
    return consultationDate && consultationDate > todayIso(now)
      ? "La fecha de seguimiento tiene que ser posterior a la consulta."
      : "La fecha de seguimiento tiene que ser posterior a hoy.";
  }
  return null;
}

/** "Sugerido: subsecuente (2 consultas anteriores con I10)". */
export function describeSuggestion(
  suggestion: ConsultationMorbidity | null,
  previousConsultations: number,
  cieCode: string | null,
): string | null {
  if (!suggestion || !cieCode) return null;
  if (suggestion === "1") return `Sugerido: primera vez (sin consultas anteriores con ${cieCode}).`;
  const plural = previousConsultations === 1 ? "consulta anterior" : "consultas anteriores";
  return `Sugerido: subsecuente (${previousConsultations} ${plural} con ${cieCode}).`;
}
