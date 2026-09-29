import type { ArcoRequestStatus, ArcoRequestType, ArcoRequesterRelation } from "@api/types";

export const ARCO_TYPE_LABELS: Record<ArcoRequestType, string> = {
  A: "Acceso",
  R: "Rectificación",
  C: "Cancelación",
  O: "Oposición",
};

export const ARCO_STATUS_LABELS: Record<ArcoRequestStatus, string> = {
  recibida: "Recibida",
  en_proceso: "En proceso",
  procedente: "Procedente",
  improcedente: "Improcedente",
};

export const ARCO_RELATION_LABELS: Record<ArcoRequesterRelation, string> = {
  titular: "Titular de los datos",
  representante: "Representante legal",
};

export const ARCO_STATUS_BADGE_VARIANT: Record<
  ArcoRequestStatus,
  "outline" | "secondary" | "critical"
> = {
  recibida: "outline",
  en_proceso: "outline",
  procedente: "secondary",
  improcedente: "critical",
};

export const isArcoRequestFinal = (status: ArcoRequestStatus) =>
  status === "procedente" || status === "improcedente";

/** "2026-10-23" -> "23/10/2026" sin pasar por Date (evita el corrimiento
 * de zona horaria de `new Date("AAAA-MM-DD")`, que se interpreta en UTC). */
export function formatArcoDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : "—";
}
