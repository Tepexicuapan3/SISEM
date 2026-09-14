import * as z from "zod";

const requiredText = (label: string, maxLength = 200) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

const optionalText = (maxLength = 200) =>
  z.string().trim().max(maxLength).optional().or(z.literal(""));

export const destinoAmbulanciaDetailsSchema = z.object({
  name: requiredText("Nombre", 200),
  street: optionalText(200),
  zipCode: optionalText(10),
  neighborhood: optionalText(150),
  borough: optionalText(150),
  phone: optionalText(40),
  reference: optionalText(1000),
});

export const createDestinoAmbulanciaSchema = destinoAmbulanciaDetailsSchema;

export type DestinoAmbulanciaDetailsFormValues = z.infer<typeof destinoAmbulanciaDetailsSchema>;
export type CreateDestinoAmbulanciaFormValues = z.infer<typeof createDestinoAmbulanciaSchema>;
