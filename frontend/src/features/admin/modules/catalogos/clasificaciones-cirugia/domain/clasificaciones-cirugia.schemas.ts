import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const clasificacionCirugiaDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
});

export const createClasificacionCirugiaSchema = clasificacionCirugiaDetailsSchema;

export type ClasificacionCirugiaDetailsFormValues = z.infer<typeof clasificacionCirugiaDetailsSchema>;
export type CreateClasificacionCirugiaFormValues = z.infer<typeof createClasificacionCirugiaSchema>;
