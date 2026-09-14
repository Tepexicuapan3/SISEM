import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const motivoCancelacionCirugiaDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
});

export const createMotivoCancelacionCirugiaSchema = motivoCancelacionCirugiaDetailsSchema;

export type MotivoCancelacionCirugiaDetailsFormValues = z.infer<typeof motivoCancelacionCirugiaDetailsSchema>;
export type CreateMotivoCancelacionCirugiaFormValues = z.infer<typeof createMotivoCancelacionCirugiaSchema>;
