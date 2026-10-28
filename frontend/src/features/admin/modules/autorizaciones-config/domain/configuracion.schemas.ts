import * as z from "zod";

// Mismas reglas C1-C4 que configuracion_use_case (UX; el servidor decide).

export const MODALIDADES = ["PRIMERO_VALIDO", "MULTIPLE"] as const;
export const AMBITOS = ["RECHAZO", "SUSPENSION", "BAJA", "CANCELACION"] as const;

const aprobaciones = z
  .number({ error: "Indica un número" })
  .int({ error: "Debe ser entero" })
  .min(1, { error: "Mínimo 1" })
  .max(10, { error: "Máximo 10" });
const horas = z
  .number({ error: "Indica un número" })
  .int({ error: "Debe ser entero" })
  .min(1, { error: "Mínimo 1 hora" });

const PRIMERO_VALIDO_UNA = "Con «primero válido» basta una aprobación";

export const tipoSchema = z
  .object({
    modalidadPredeterminada: z.enum(MODALIDADES),
    aprobacionesRequeridas: aprobaciones,
    horasVigenciaSolicitud: horas,
    horasEscalamiento: horas,
    permiteRechazo: z.boolean(),
    rechazoResuelveSolicitud: z.boolean(),
    requiereCedula: z.boolean(),
  })
  .superRefine((valores, ctx) => {
    if (valores.modalidadPredeterminada === "PRIMERO_VALIDO" && valores.aprobacionesRequeridas !== 1) {
      ctx.addIssue({ code: "custom", path: ["aprobacionesRequeridas"], message: PRIMERO_VALIDO_UNA });
    }
    if (valores.horasEscalamiento >= valores.horasVigenciaSolicitud) {
      ctx.addIssue({
        code: "custom",
        path: ["horasEscalamiento"],
        message: "El escalamiento debe ocurrir antes de que venza la solicitud",
      });
    }
  });

export type TipoFormValues = z.infer<typeof tipoSchema>;

export const reglaCentroSchema = z
  .object({
    tipoId: z.number().int().min(1, { error: "Selecciona el tipo" }),
    centroId: z.number().int().min(1, { error: "Selecciona el centro" }),
    modalidad: z.enum(MODALIDADES).nullable(),
    aprobacionesRequeridas: aprobaciones.nullable(),
    horasVigenciaSolicitud: horas.nullable(),
  })
  .superRefine((valores, ctx) => {
    const sinValores =
      valores.modalidad === null &&
      valores.aprobacionesRequeridas === null &&
      valores.horasVigenciaSolicitud === null;
    if (sinValores) {
      ctx.addIssue({ code: "custom", path: ["modalidad"], message: "Define al menos un valor propio para el centro" });
    }
    if (
      valores.modalidad === "PRIMERO_VALIDO" &&
      valores.aprobacionesRequeridas !== null &&
      valores.aprobacionesRequeridas !== 1
    ) {
      ctx.addIssue({ code: "custom", path: ["aprobacionesRequeridas"], message: PRIMERO_VALIDO_UNA });
    }
  });

export type ReglaCentroFormValues = z.infer<typeof reglaCentroSchema>;

export const normalizarClaveMotivo = (clave: string) => clave.trim().replace(/\s+/g, "_").toUpperCase();

export const motivoSchema = z.object({
  ambito: z.enum(AMBITOS),
  clave: z
    .string()
    .transform(normalizarClaveMotivo)
    .pipe(z.string().regex(/^[A-Z0-9_]{2,20}$/, { error: "De 2 a 20 letras, números o guion bajo" })),
  descripcion: z
    .string()
    .trim()
    .min(1, { error: "La descripción es obligatoria" })
    .max(150, { error: "Máximo 150 caracteres" }),
  requiereDescripcionLibre: z.boolean(),
});

export type MotivoFormValues = z.input<typeof motivoSchema>;

/** Mensaje por campo a partir de los issues de un safeParse. */
export const erroresPorCampo = (issues: { path: PropertyKey[]; message: string }[]): Record<string, string> =>
  Object.fromEntries(issues.map((issue) => [String(issue.path[0]), issue.message]));
