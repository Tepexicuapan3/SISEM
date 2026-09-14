import * as z from "zod";

export const scheduleSurgerySchema = z.object({
  noExp: z.string().trim().min(1, { error: "Expediente requerido" }).max(20),
  pkNum: z.coerce.number().int().min(0).default(0),
  surgeonId: z.coerce.number().int().min(1, { error: "Selecciona un medico" }),
  surgeryTypeId: z.coerce.number().int().min(1, { error: "Selecciona un tipo de cirugia" }),
  classificationId: z.coerce.number().int().min(1, { error: "Selecciona una clasificacion" }),
  originClinicId: z.string().trim().optional().or(z.literal("")),
  scheduledDate: z.string().trim().min(1, { error: "Fecha requerida" }),
  scheduledTime: z.string().trim().min(1, { error: "Hora requerida" }),
  durationMinutes: z.coerce.number().int().min(1).optional(),
  contactPhone: z.string().trim().max(20).optional().or(z.literal("")),
  description: z.string().trim().max(2000).optional().or(z.literal("")),
  diagnosisText: z.string().trim().max(2000).optional().or(z.literal("")),
  requirements: z.string().trim().max(2000).optional().or(z.literal("")),
});

export type ScheduleSurgeryFormValues = z.infer<typeof scheduleSurgerySchema>;
export type ScheduleSurgeryFormInput = z.input<typeof scheduleSurgerySchema>;

export const cancelSurgerySchema = z.object({
  reasonId: z.coerce.number().int().min(1, { error: "Selecciona un motivo" }),
  notes: z.string().trim().max(1000).optional().or(z.literal("")),
});

export type CancelSurgeryFormValues = z.infer<typeof cancelSurgerySchema>;
export type CancelSurgeryFormInput = z.input<typeof cancelSurgerySchema>;
