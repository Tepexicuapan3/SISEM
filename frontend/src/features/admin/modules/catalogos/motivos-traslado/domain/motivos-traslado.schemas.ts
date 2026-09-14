import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const motivoTrasladoDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
  requiresNotes: z.boolean(),
});

export const createMotivoTrasladoSchema = motivoTrasladoDetailsSchema;

export type MotivoTrasladoDetailsFormValues = z.infer<typeof motivoTrasladoDetailsSchema>;
export type CreateMotivoTrasladoFormValues = z.infer<typeof createMotivoTrasladoSchema>;
