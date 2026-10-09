import type { BloodTypeRecord, BloodTypeSource } from "@api/types";

/** 5.2: de donde sale el tipo de sangre. */
export const BLOOD_TYPE_SOURCE_LABELS: Record<BloodTypeSource, string> = {
  L: "Laboratorio",
  D: "Declarado por el paciente",
};

/**
 * Texto corto para el header del expediente: "O+", o "O+ (declarado)" si
 * nadie lo confirmo con laboratorio. null si no hay registro.
 */
export function bloodTypeSummary(current: BloodTypeRecord | null | undefined): string | null {
  if (!current) return null;
  return current.source === "D" ? `${current.bloodTypeName} (declarado)` : current.bloodTypeName;
}

export type BloodTypeChange = "none" | "capture" | "correction";

/**
 * Que pasa si se guarda `next`: nada (igual al vigente), primera captura, o
 * correccion de uno vigente -- la correccion exige motivo (bitacora).
 */
export function classifyBloodTypeChange(
  current: Pick<BloodTypeRecord, "bloodTypeId" | "source"> | null | undefined,
  next: { bloodTypeId: number | null; source: BloodTypeSource },
): BloodTypeChange {
  if (next.bloodTypeId === null) return "none";
  if (!current) return "capture";
  return current.bloodTypeId === next.bloodTypeId && current.source === next.source ? "none" : "correction";
}
