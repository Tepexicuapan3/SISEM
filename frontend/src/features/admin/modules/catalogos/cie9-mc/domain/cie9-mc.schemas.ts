import * as z from "zod";

const requiredText = (label: string, maxLength = 120) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const cie9McDetailsSchema = z.object({
  name: requiredText("Descripción", 400),
  code: requiredText("Clave", 10),
});

export const createCie9McSchema = cie9McDetailsSchema;

export type Cie9McDetailsFormValues = z.infer<typeof cie9McDetailsSchema>;
export type CreateCie9McFormValues = z.infer<typeof createCie9McSchema>;
