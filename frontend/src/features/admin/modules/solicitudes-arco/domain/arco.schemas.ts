import * as z from "zod";

export const createSolicitudArcoSchema = z.object({
  type: z.enum(["A", "R", "C", "O"], {
    error: "Selecciona el tipo de derecho",
  }),
  noExp: z.string().trim().min(1, { error: "Indica el expediente" }).max(20, { error: "Maximo 20 caracteres" }),
  pkNum: z.string().trim().regex(/^\d+$/, { error: "Debe ser un numero" }),
  requesterName: z.string().trim().min(1, { error: "Indica el nombre del solicitante" }).max(255),
  requesterRelation: z.enum(["titular", "representante"]),
  requesterEmail: z.union([z.literal(""), z.email({ error: "Correo invalido" })]),
  requesterPhone: z.string().trim().max(50, { error: "Maximo 50 caracteres" }),
  description: z.string().trim().min(1, { error: "Describe lo que se solicita" }).max(4000),
  receivedDate: z.string().min(1, { error: "Indica la fecha de recepcion" }),
  transparencyFolio: z.string().trim().max(50, { error: "Maximo 50 caracteres" }),
});

export type CreateSolicitudArcoFormValues = z.infer<typeof createSolicitudArcoSchema>;

export const changeSolicitudArcoStatusSchema = z
  .object({
    status: z.enum(["en_proceso", "procedente", "improcedente"]),
    response: z.string().trim().max(4000, { error: "Maximo 4000 caracteres" }),
  })
  .refine((values) => values.status === "en_proceso" || values.response.length > 0, {
    error: "La respuesta es obligatoria para resolver la solicitud",
    path: ["response"],
  });

export type ChangeSolicitudArcoStatusFormValues = z.infer<typeof changeSolicitudArcoStatusSchema>;
