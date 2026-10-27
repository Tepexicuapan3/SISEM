import * as z from "zod";

export const CLAVES_TIPO = ["LAB", "GAB", "REC", "CNO"] as const;
export const TIPOS_CENTRO = ["CLINICA", "HOSPITAL", "INSTITUTO"] as const;

const fechaIsoOVacia = z.union([
  z.string().regex(/^\d{4}-\d{2}-\d{2}$/, { error: "Fecha inválida" }),
  z.literal(""),
]);

const alcanceSchema = z.object({
  centros: z.array(z.number()),
  tiposCentro: z.array(z.enum(TIPOS_CENTRO)),
  global: z.boolean(),
});

const tipoSchema = z.object({
  clave: z.enum(CLAVES_TIPO),
  seleccionado: z.boolean(),
  alcance: alcanceSchema,
});

export interface AutorizadorSchemaOptions {
  /** `admin:autorizadores:global`: sin el, "Todos los centros" no se puede otorgar. */
  canGrantGlobal: boolean;
  /** En la edicion el usuario y la vigencia no se cambian (la vigencia se renueva aparte). */
  modo: "alta" | "edicion";
}

/**
 * Reglas espejo del backend (UX; el servidor decide):
 * - alta: usuario elegido y vigencia con fin >= inicio
 * - al menos un tipo de autorizacion
 * - cada tipo elegido con al menos un centro, tipo de centro o todos los centros
 * - todos los centros exige el permiso global
 */
export const buildAutorizadorSchema = ({ canGrantGlobal, modo }: AutorizadorSchemaOptions) =>
  z
    .object({
      usuarioId: z.number(),
      cargo: z.string().max(80, { error: "Máximo 80 caracteres" }),
      numeroOficio: z.string().max(100, { error: "Máximo 100 caracteres" }),
      fechaInicioVigencia: fechaIsoOVacia,
      fechaFinVigencia: fechaIsoOVacia,
      tipos: z.array(tipoSchema),
    })
    .superRefine((valores, ctx) => {
      if (modo === "alta") {
        if (valores.usuarioId < 1) {
          ctx.addIssue({ code: "custom", path: ["usuarioId"], message: "Selecciona un usuario" });
        }
        if (!valores.fechaInicioVigencia) {
          ctx.addIssue({
            code: "custom",
            path: ["fechaInicioVigencia"],
            message: "Fecha de inicio requerida",
          });
        }
        if (!valores.fechaFinVigencia) {
          ctx.addIssue({
            code: "custom",
            path: ["fechaFinVigencia"],
            message: "Fecha de fin requerida",
          });
        } else if (
          valores.fechaInicioVigencia &&
          valores.fechaFinVigencia < valores.fechaInicioVigencia
        ) {
          ctx.addIssue({
            code: "custom",
            path: ["fechaFinVigencia"],
            message: "La fecha de fin no puede ser anterior a la de inicio",
          });
        }
      }

      if (!valores.tipos.some((tipo) => tipo.seleccionado)) {
        ctx.addIssue({
          code: "custom",
          path: ["tipos"],
          message: "Elige al menos un tipo de autorización",
        });
      }

      valores.tipos.forEach((tipo, indice) => {
        if (!tipo.seleccionado) return;
        const { centros, tiposCentro, global } = tipo.alcance;
        if (global && !canGrantGlobal) {
          ctx.addIssue({
            code: "custom",
            path: ["tipos", indice, "alcance"],
            message: "No tienes permiso para otorgar todos los centros",
          });
        } else if (!global && centros.length === 0 && tiposCentro.length === 0) {
          ctx.addIssue({
            code: "custom",
            path: ["tipos", indice, "alcance"],
            message: "Selecciona al menos un centro o un tipo de centro",
          });
        }
      });
    });

export type AutorizadorFormValues = z.infer<ReturnType<typeof buildAutorizadorSchema>>;
export type TipoFormValue = AutorizadorFormValues["tipos"][number];
