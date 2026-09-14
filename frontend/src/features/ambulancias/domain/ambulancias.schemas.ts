import * as z from "zod";

export const ambulanceScheduleItemSchema = z.object({
  transferDate: z.string().trim().min(1, { error: "Fecha requerida" }),
  transferTime: z.string().trim().min(1, { error: "Hora requerida" }),
  transferTypeId: z.coerce.number().int().min(1, { error: "Selecciona un tipo de traslado" }),
  serviceTypeId: z.coerce.number().int().min(1, { error: "Selecciona un tipo de servicio" }),
});

export const createAmbulanceRequestSchema = z
  .object({
    noExp: z.string().trim().min(1, { error: "Expediente requerido" }).max(20),
    pkNum: z.coerce.number().int().min(0).default(0),
    requestingClinicId: z.string().trim().min(1, { error: "Selecciona una clinica" }),
    requestedByName: z.string().trim().min(1, { error: "Nombre requerido" }).max(200),
    requestedByRelationshipId: z.string().trim().optional().or(z.literal("")),
    socialWorkNotes: z.string().trim().max(1000).optional().or(z.literal("")),
    reasonId: z.coerce.number().int().min(1, { error: "Selecciona un motivo" }),
    reasonNotes: z.string().trim().max(1000).optional().or(z.literal("")),
    diagnosisText: z.string().trim().max(1000).optional().or(z.literal("")),
    originStreet: z.string().trim().max(200).optional().or(z.literal("")),
    originZip: z.string().trim().max(10).optional().or(z.literal("")),
    originNeighborhood: z.string().trim().max(150).optional().or(z.literal("")),
    originBorough: z.string().trim().max(150).optional().or(z.literal("")),
    originPhone: z.string().trim().max(40).optional().or(z.literal("")),
    originReference: z.string().trim().max(1000).optional().or(z.literal("")),
    destinationId: z.coerce.number().int().min(1, { error: "Selecciona un destino" }),
    schedules: z.array(ambulanceScheduleItemSchema).min(1, { error: "Agrega al menos una fecha de traslado" }),
  });

export type CreateAmbulanceRequestFormValues = z.infer<typeof createAmbulanceRequestSchema>;
export type CreateAmbulanceRequestFormInput = z.input<typeof createAmbulanceRequestSchema>;

export const authorizeAmbulanceRequestSchema = z.object({
  serviceNumber: z.string().trim().min(1, { error: "Numero de servicio requerido" }).max(30),
});
export type AuthorizeAmbulanceRequestFormValues = z.infer<typeof authorizeAmbulanceRequestSchema>;

export const rejectAmbulanceRequestSchema = z.object({
  notes: z.string().trim().min(1, { error: "Indica el motivo del rechazo" }).max(1000),
});
export type RejectAmbulanceRequestFormValues = z.infer<typeof rejectAmbulanceRequestSchema>;
