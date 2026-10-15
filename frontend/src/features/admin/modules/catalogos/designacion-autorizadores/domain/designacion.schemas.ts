import * as z from "zod";

const requiredFk = (label: string) =>
  z.number({ error: `${label} requerido` }).min(1, { error: `${label} requerido` });

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, { error: "Fecha invalida" });

export const TIPOS_CENTRO = ["CLINICA", "HOSPITAL", "INSTITUTO"] as const;

export interface DesignacionSchemaOptions {
  /** Solo quien tiene `admin.catalogs.designacionAutorizadores.global` puede otorgar GLOBAL. */
  canGrantGlobal: boolean;
}

/**
 * Reglas espejo del backend (UX gating; el backend decide):
 * - alcance con al menos un item (centro | tipo | GLOBAL explicito)
 * - GLOBAL exclusivo (el backend responde 400 si se combina)
 * - GLOBAL exige fecha fin y permiso global
 * - fecha fin >= fecha inicio
 */
export const buildDesignacionSchema = ({ canGrantGlobal }: DesignacionSchemaOptions) =>
  z
    .object({
      userId: requiredFk("Usuario"),
      tipoAutorizacionId: requiredFk("Tipo de autorización"),
      cargo: z
        .string()
        .trim()
        .min(1, { error: "Cargo requerido" })
        .max(60, { error: "Máximo 60 caracteres" }),
      fechaInicio: isoDate,
      fechaFin: z.union([isoDate, z.literal("")]),
      oficio: z.string().trim().max(100, { error: "Máximo 100 caracteres" }),
      centros: z.array(z.number()),
      tiposCentro: z.array(z.enum(TIPOS_CENTRO)),
      global: z.boolean(),
    })
    .superRefine((values, ctx) => {
      const hasItems = values.centros.length > 0 || values.tiposCentro.length > 0;

      if (values.global) {
        if (!canGrantGlobal) {
          ctx.addIssue({
            code: "custom",
            path: ["global"],
            message: "No tienes permiso para otorgar alcance de todos los centros",
          });
        }
        if (hasItems) {
          ctx.addIssue({
            code: "custom",
            path: ["global"],
            message: "Todos los centros no se combina con otros centros o tipos",
          });
        }
        if (!values.fechaFin) {
          ctx.addIssue({
            code: "custom",
            path: ["fechaFin"],
            message: "La fecha fin es obligatoria cuando el alcance es todos los centros",
          });
        }
      } else if (!hasItems) {
        ctx.addIssue({
          code: "custom",
          path: ["centros"],
          message: "Selecciona al menos un centro o un tipo de centro",
        });
      }

      if (values.fechaFin && values.fechaFin < values.fechaInicio) {
        ctx.addIssue({
          code: "custom",
          path: ["fechaFin"],
          message: "La fecha fin no puede ser anterior a la fecha inicio",
        });
      }
    });

export type DesignacionFormValues = z.infer<ReturnType<typeof buildDesignacionSchema>>;
