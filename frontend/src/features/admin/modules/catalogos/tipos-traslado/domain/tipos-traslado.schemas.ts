import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const tipoTrasladoDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
});

export const createTipoTrasladoSchema = tipoTrasladoDetailsSchema;

export type TipoTrasladoDetailsFormValues = z.infer<typeof tipoTrasladoDetailsSchema>;
export type CreateTipoTrasladoFormValues = z.infer<typeof createTipoTrasladoSchema>;
