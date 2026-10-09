import * as z from "zod";
import { followUpError } from "./consultation-morbidity";

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
  // Documento 5.3 (sw_morbi y fe_cita). Morbilidad obligatoria solo para
  // cerrar: la exige canCloseSelectedVisit y el backend, no el guardado de avance.
  morbidity: z.enum(["", "1", "2"]),
  followUpEnabled: z.boolean(),
  followUpDate: z.string(),
});

export const saveDiagnosisFormSchema = diagnosisFieldsSchema.superRefine((values, ctx) => {
  const message = followUpError(values.followUpEnabled, values.followUpDate);
  if (message) {
    ctx.addIssue({ code: "custom", path: ["followUpDate"], message });
  }
});

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
