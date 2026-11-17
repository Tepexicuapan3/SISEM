import * as z from "zod";

const optionalText = (max: number) => z.string().trim().max(max).optional().or(z.literal(""));
// Fecha LOCAL (toISOString es UTC: despues de las 18:00 en CDMX ya seria manana).
export const todayLocalISO = () => {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};
const today = todayLocalISO;
const notFuture = (value: string | undefined) => !value || value <= today();

export const enrollPadronSchema = z.object({
  noExp: z.string().trim().min(1, { error: "Expediente requerido" }).max(20),
  // Sale de elegir a la persona entre los miembros del expediente, no se escribe.
  pkNum: z.number({ error: "Selecciona a la persona" }).int().min(0),
  itemId: z.string().trim().min(1, { error: "Selecciona el padecimiento" }),
  enrolledOn: optionalText(10).refine(notFuture, { error: "La fecha no puede ser futura" }),
  notes: optionalText(500),
});

export const dischargePadronSchema = z.object({
  reasonId: z.coerce.number().int().min(1, { error: "Selecciona un motivo" }),
  detail: optionalText(500),
  dischargedOn: optionalText(10).refine(notFuture, { error: "La fecha no puede ser futura" }),
});

// Corregir (docs/plans/padrones-correccion-y-prioridad.md): vacío = se conserva.
export const correctPadronSchema = z.object({
  itemId: optionalText(20),
  enrolledOn: optionalText(10).refine(notFuture, { error: "La fecha no puede ser futura" }),
  notes: optionalText(500),
  detail: z.string().trim().min(1, { error: "Indica qué se corrigió" }).max(400),
});

export type EnrollPadronFormValues = z.input<typeof enrollPadronSchema>;
export type CorrectPadronFormValues = z.input<typeof correctPadronSchema>;
export type DischargePadronFormValues = z.input<typeof dischargePadronSchema>;
