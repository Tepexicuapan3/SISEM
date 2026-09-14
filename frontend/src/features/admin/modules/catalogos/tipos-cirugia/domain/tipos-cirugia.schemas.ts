import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const tipoCirugiaDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
});

export const createTipoCirugiaSchema = tipoCirugiaDetailsSchema;

export type TipoCirugiaDetailsFormValues = z.infer<typeof tipoCirugiaDetailsSchema>;
export type CreateTipoCirugiaFormValues = z.infer<typeof createTipoCirugiaSchema>;
