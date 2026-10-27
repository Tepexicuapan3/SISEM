import * as z from "zod";
import type { MotivoRechazo } from "@api/types/autorizaciones/solicitudes.types";

/**
 * Reglas espejo del backend (UX; el servidor vuelve a validar todo):
 * - toda decision se firma con la contraseña propia
 * - rechazar exige motivo tipificado; "Otro" exige descripcion
 */
export const buildDecisionSchema = (motivos: MotivoRechazo[]) =>
  z
    .object({
      decision: z.enum(["APROBAR", "RECHAZAR"]),
      motivoId: z.number(),
      descripcionMotivo: z.string().max(500, { error: "Máximo 500 caracteres" }),
      credencial: z.string(),
    })
    .superRefine((valores, ctx) => {
      if (!valores.credencial) {
        ctx.addIssue({
          code: "custom",
          path: ["credencial"],
          message: "Escribe tu contraseña para firmar la decisión",
        });
      }
      if (valores.decision !== "RECHAZAR") return;
      const motivo = motivos.find((m) => m.id === valores.motivoId);
      if (!motivo) {
        ctx.addIssue({ code: "custom", path: ["motivoId"], message: "Selecciona el motivo del rechazo" });
      } else if (motivo.requiereDescripcionLibre && !valores.descripcionMotivo.trim()) {
        ctx.addIssue({ code: "custom", path: ["descripcionMotivo"], message: "Describe el motivo del rechazo" });
      }
    });

export type DecisionFormValues = z.infer<ReturnType<typeof buildDecisionSchema>>;
