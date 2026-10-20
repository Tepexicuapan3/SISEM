import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const motivoBajaPadronDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
});

export const createMotivoBajaPadronSchema = motivoBajaPadronDetailsSchema;

export type MotivoBajaPadronDetailsFormValues = z.infer<typeof motivoBajaPadronDetailsSchema>;
export type CreateMotivoBajaPadronFormValues = z.infer<typeof createMotivoBajaPadronSchema>;
