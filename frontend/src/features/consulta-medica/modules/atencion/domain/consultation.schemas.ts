import * as z from "zod";

const diagnosisFieldsSchema = z.object({
  primaryDiagnosis: z
    .string()
    .trim()
    .min(1, { error: "Ingresa el diagnostico principal." }),
  finalNote: z.string().trim().min(1, { error: "Ingresa la nota final." }),
  cieCode: z
    .string()
    .trim()
    .max(8, { error: "La clave CIE debe tener maximo 8 caracteres." }),
  // his_notas ampliada (documento "Historia Clinica Unificada", 5.2): opcionales.
  currentIllness: z.string().trim(),
  systemsReview: z.string().trim(),
  diagnosticPlan: z.string().trim(),
  therapeuticPlan: z.string().trim(),
});

export const saveDiagnosisFormSchema = diagnosisFieldsSchema;

export type SaveDiagnosisFormValues = z.infer<typeof saveDiagnosisFormSchema>;
export type SaveDiagnosisFormInput = z.input<typeof saveDiagnosisFormSchema>;

export const savePrescriptionsFormSchema = z.object({
  itemsText: z
    .string()
    .trim()
    .min(1, { error: "Ingresa al menos una indicacion de receta." }),
});

export type SavePrescriptionsFormValues = z.infer<
  typeof savePrescriptionsFormSchema
>;
export type SavePrescriptionsFormInput = z.input<
  typeof savePrescriptionsFormSchema
>;
