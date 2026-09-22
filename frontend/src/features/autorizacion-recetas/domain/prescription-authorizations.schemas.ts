import * as z from "zod";

export const rejectPrescriptionSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, { error: "Indica el motivo del rechazo" })
    .max(500, { error: "Maximo 500 caracteres" }),
});

export type RejectPrescriptionFormValues = z.infer<typeof rejectPrescriptionSchema>;
