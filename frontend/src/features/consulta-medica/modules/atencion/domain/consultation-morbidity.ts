import type { ConsultationMorbidity } from "@api/types";

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

/** Primer dia valido para el seguimiento: mañana. */
export function minFollowUpDate(now: Date = new Date()): string {
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  return todayIso(tomorrow);
}

/**
 * Regla del legado: si el medico marca "cita", la fecha es obligatoria.
 * Mejora: tiene que ser posterior a hoy. null si esta bien.
 */
export function followUpError(enabled: boolean, date: string, now: Date = new Date()): string | null {
  if (!enabled) return null;
  if (!date) return "Indica la fecha de seguimiento.";
  if (date <= todayIso(now)) return "La fecha de seguimiento tiene que ser posterior a hoy.";
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
