import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const motivoCancelacionNotaDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
});

export const createMotivoCancelacionNotaSchema = motivoCancelacionNotaDetailsSchema;

export type MotivoCancelacionNotaDetailsFormValues = z.infer<typeof motivoCancelacionNotaDetailsSchema>;
export type CreateMotivoCancelacionNotaFormValues = z.infer<typeof createMotivoCancelacionNotaSchema>;
