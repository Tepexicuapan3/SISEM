import * as z from "zod";

export const CUADRO_BASICO_OPTIONS = [
  { value: "BASICO", label: "Cuadro básico" },
  { value: "ESPECIAL", label: "Especial" },
  { value: "INSTITUCIONAL", label: "Institucional" },
] as const;

export const CUADRO_BASICO_LABEL: Record<string, string> = {
  BASICO: "Básico",
  ESPECIAL: "Especial",
  INSTITUCIONAL: "Institucional",
};

const optionalText = (maxLength: number) => z.string().trim().max(maxLength);

export const medicamentoDetailsSchema = z.object({
  name: z.string().trim().min(1, { error: "Nombre requerido" }).max(150),
  code: optionalText(30),
  genericName: optionalText(150),
  presentation: optionalText(150),
  cuadroBasico: z.enum(["BASICO", "ESPECIAL", "INSTITUCIONAL"]),
  isControlled: z.boolean(),
  // Vacio = sin tope; si se captura, entero mayor a 0 (mismo criterio que el import).
  maxQuantity: z
    .string()
    .trim()
    .regex(/^([1-9]\d*)?$/, { error: "Debe ser un entero mayor a 0" }),
});

export const createMedicamentoSchema = medicamentoDetailsSchema;

export type MedicamentoDetailsFormValues = z.infer<typeof medicamentoDetailsSchema>;
export type CreateMedicamentoFormValues = z.infer<typeof createMedicamentoSchema>;
