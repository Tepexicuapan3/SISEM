import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

export const tipoServicioAmbulanciaDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
});

export const createTipoServicioAmbulanciaSchema = tipoServicioAmbulanciaDetailsSchema;

export type TipoServicioAmbulanciaDetailsFormValues = z.infer<typeof tipoServicioAmbulanciaDetailsSchema>;
export type CreateTipoServicioAmbulanciaFormValues = z.infer<typeof createTipoServicioAmbulanciaSchema>;
