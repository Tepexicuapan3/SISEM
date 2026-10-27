import * as z from "zod";
import type { AutorizadorItem, MotivoCatalogo } from "@api/types/autorizaciones/autorizadores.types";

export interface AccionesAutorizador {
  editar: boolean;
  renovar: boolean;
  suspender: boolean;
  reactivar: boolean;
  darDeBaja: boolean;
}

/**
 * Transiciones de estatus que el backend acepta (UX; el servidor decide):
 * ACTIVO <-> SUSPENDIDO; ACTIVO|SUSPENDIDO -> INACTIVO (terminal).
 */
export const accionesDisponibles = (item: Pick<AutorizadorItem, "estatus">): AccionesAutorizador => {
  switch (item.estatus) {
    case "ACTIVO":
      return { editar: true, renovar: true, suspender: true, reactivar: false, darDeBaja: true };
    case "SUSPENDIDO":
      return { editar: true, renovar: true, suspender: false, reactivar: true, darDeBaja: true };
    default:
      return { editar: false, renovar: false, suspender: false, reactivar: false, darDeBaja: false };
  }
};

const fechaIsoOVacia = z.union([
  z.string().regex(/^\d{4}-\d{2}-\d{2}$/, { error: "Fecha inválida" }),
  z.literal(""),
]);

/** Suspension o baja: motivo tipificado; "Otro" exige descripcion. */
export const buildCambioEstatusSchema = (motivos: MotivoCatalogo[]) =>
  z
    .object({
      motivoId: z.number(),
      descripcionMotivo: z.string().max(255, { error: "Máximo 255 caracteres" }),
      fechaFinSuspension: fechaIsoOVacia,
    })
    .superRefine((valores, ctx) => {
      const motivo = motivos.find((m) => m.id === valores.motivoId);
      if (!motivo) {
        ctx.addIssue({ code: "custom", path: ["motivoId"], message: "Selecciona un motivo" });
        return;
      }
      if (motivo.requiereDescripcionLibre && !valores.descripcionMotivo.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["descripcionMotivo"],
          message: "Describe el motivo",
        });
      }
    });

export type CambioEstatusFormValues = z.infer<ReturnType<typeof buildCambioEstatusSchema>>;

/** Renovar solo amplia: la nueva fecha debe ser posterior al fin actual. */
export const buildRenovacionSchema = (finActual: string) =>
  z.object({
    fechaFinVigencia: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, { error: "Fecha inválida" })
      .refine((valor) => valor > finActual, {
        error: "La nueva fecha debe ser posterior a la vigencia actual",
      }),
  });

export type RenovacionFormValues = z.infer<ReturnType<typeof buildRenovacionSchema>>;
