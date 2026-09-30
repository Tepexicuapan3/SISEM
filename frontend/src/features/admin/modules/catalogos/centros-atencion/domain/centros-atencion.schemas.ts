import * as z from "zod";

const requiredText = (label: string, maxLength = 160) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength);

const optionalText = (maxLength = 255) =>
  z
    .string()
    .trim()
    .max(maxLength)
    .optional()
    .nullable()
    .transform((value) => {
      if (value == null) return null;
      return value === "" ? null : value;
    });

const optionalPostalCode = z
  .string()
  .trim()
  .regex(/^\d{5}$/, { error: "Codigo postal invalido" })
  .optional()
  .nullable()
  .or(z.literal(""))
  .transform((value) => {
    if (value == null || value === "") return null;
    return value;
  });

const optionalTime = (label: string) =>
  z
    .string()
    .trim()
    .regex(/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/, {
      error: `${label} invalido`,
    })
    .optional()
    .nullable()
    .or(z.literal(""))
    .transform((value) => {
      if (value == null || value === "") return null;
      return value.length === 5 ? `${value}:00` : value;
    });

// =============================================================================
// CENTRO DE ATENCION
// =============================================================================

export const centroAtencionDetailsSchema = z.object({
  name: requiredText("Nombre", 120),
  code: requiredText("CLUES", 50),
  centerType: z.enum(["CLINICA", "HOSPITAL", "INSTITUTO"], {
    error: "Tipo de centro invalido",
  }),
  legacyFolio: optionalText(10),
  isExternal: z.boolean(),

  address: optionalText(255),
  postalCode: optionalPostalCode,
  neighborhood: optionalText(120),
  municipality: optionalText(120),
  state: optionalText(120),
  city: optionalText(120),
  phone: optionalText(40),

  isActive: z.boolean().default(true),
});

export const createCentroAtencionSchema = centroAtencionDetailsSchema;

export const updateCentroAtencionSchema = centroAtencionDetailsSchema.partial();

// =============================================================================
// HORARIO DE CENTRO
// =============================================================================

export const centroAtencionHorarioSchema = z
  .object({
    centerId: z.number().int().positive({ error: "Centro requerido" }),
    shiftId: z.number().int().positive({ error: "Turno requerido" }),
    weekDay: z
      .number()
      .int()
      .min(1, { error: "Dia de semana invalido" })
      .max(7, { error: "Dia de semana invalido" }),

    isOpen: z.boolean(),
    is24Hours: z.boolean().default(false),

    openingTime: optionalTime("Hora de apertura"),
    closingTime: optionalTime("Hora de cierre"),
    observations: optionalText(255),
    isActive: z.boolean().default(true),
  })
  .superRefine((data, ctx) => {
    if (!data.isOpen) {
      if (data.is24Hours) {
        ctx.addIssue({
          code: "custom",
          path: ["is24Hours"],
          message: "Si esta cerrado, no puede marcarse como 24 horas",
        });
      }

      if (data.openingTime || data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Si esta cerrado, no debe capturar horas",
        });
      }

      return;
    }

    if (data.isOpen && data.is24Hours) {
      if (data.openingTime || data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Si es 24 horas, no debe capturar hora de apertura ni cierre",
        });
      }

      return;
    }

    if (data.isOpen && !data.is24Hours) {
      if (!data.openingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Hora de apertura requerida",
        });
      }

      if (!data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "Hora de cierre requerida",
        });
      }

      if (
        data.openingTime &&
        data.closingTime &&
        data.openingTime >= data.closingTime
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "La hora de cierre debe ser mayor a la hora de apertura",
        });
      }
    }
  });

// =============================================================================
// EXCEPCION DE CENTRO
// =============================================================================

export const centroAtencionExcepcionSchema = z
  .object({
    centerId: z.number().int().positive({ error: "Centro requerido" }),
    date: z
      .string()
      .trim()
      .regex(/^\d{4}-\d{2}-\d{2}$/, { error: "Fecha invalida (YYYY-MM-DD)" }),
    tipo: z.enum(["CERRADO", "HORARIO_MODIFICADO", "AVISO"], {
      error: "Tipo de excepcion invalido",
    }),
    reason: z
      .string()
      .trim()
      .min(1, { error: "Motivo requerido" })
      .max(255, { error: "Motivo demasiado largo" }),
    openingTime: optionalTime("Hora de apertura"),
    closingTime: optionalTime("Hora de cierre"),
    isActive: z.boolean().default(true),
  })
  .superRefine((data, ctx) => {
    if (data.tipo === "HORARIO_MODIFICADO") {
      if (!data.openingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Hora de apertura requerida para horario modificado",
        });
      }

      if (!data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "Hora de cierre requerida para horario modificado",
        });
      }

      if (
        data.openingTime &&
        data.closingTime &&
        data.openingTime >= data.closingTime
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "La hora de cierre debe ser mayor a la hora de apertura",
        });
      }
    } else {
      if (data.openingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Solo el tipo Horario modificado puede incluir hora de apertura",
        });
      }

      if (data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "Solo el tipo Horario modificado puede incluir hora de cierre",
        });
      }
    }
  });

export const createCentroAtencionExcepcionSchema = centroAtencionExcepcionSchema;

// =============================================================================
// TYPES
// =============================================================================

export type CentroAtencionDetailsFormValues = z.input<
  typeof centroAtencionDetailsSchema
>;

export type CreateCentroAtencionFormValues = z.input<
  typeof createCentroAtencionSchema
>;

export type UpdateCentroAtencionFormValues = z.input<
  typeof updateCentroAtencionSchema
>;

export type CentroAtencionHorarioFormValues = z.input<
  typeof centroAtencionHorarioSchema
>;

export type CentroAtencionExcepcionFormValues = z.input<
  typeof centroAtencionExcepcionSchema
>;

export type CreateCentroAtencionExcepcionFormValues = z.input<
  typeof createCentroAtencionExcepcionSchema
>;

// =============================================================================
// WEEK HORARIO (grilla semanal — todos los días a la vez)
// =============================================================================

export const weekDayRowSchema = z
  .object({
    weekDay: z.number().int().min(1).max(7),
    existingId: z.number().int().positive().optional(),
    isOpen: z.boolean(),
    is24Hours: z.boolean(),
    openingTime: optionalTime("Hora de apertura"),
    closingTime: optionalTime("Hora de cierre"),
    observations: optionalText(255),
  })
  .superRefine((data, ctx) => {
    if (!data.isOpen) return;
    if (data.is24Hours) {
      if (data.openingTime || data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Si es 24 horas, no capture horas",
        });
      }
      return;
    }
    if (!data.openingTime) {
      ctx.addIssue({
        code: "custom",
        path: ["openingTime"],
        message: "Hora de apertura requerida",
      });
    }
    if (!data.closingTime) {
      ctx.addIssue({
        code: "custom",
        path: ["closingTime"],
        message: "Hora de cierre requerida",
      });
    }
    if (
      data.openingTime &&
      data.closingTime &&
      data.openingTime >= data.closingTime
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["closingTime"],
        message: "La hora de cierre debe ser mayor a la apertura",
      });
    }
  });

export const weekHorarioFormSchema = z.object({
  centerId: z.number().int().positive({ error: "Centro requerido" }),
  shiftId: z.number().int().positive({ error: "Turno requerido" }),
  days: z.array(weekDayRowSchema).length(7),
});

export type WeekDayRowFormValues = z.input<typeof weekDayRowSchema>;
export type WeekHorarioFormValues = z.input<typeof weekHorarioFormSchema>;

// =============================================================================
// BULK EXCEPCION (múltiples fechas a la vez)
// =============================================================================

export const bulkExcepcionFormSchema = z
  .object({
    centerId: z.number().int().positive({ error: "Centro requerido" }),
    dates: z
      .array(
        z
          .string()
          .trim()
          .regex(/^\d{4}-\d{2}-\d{2}$/, { error: "Fecha invalida" }),
      )
      .min(1, { error: "Selecciona al menos una fecha" }),
    tipo: z.enum(["CERRADO", "HORARIO_MODIFICADO", "AVISO"], {
      error: "Tipo invalido",
    }),
    reason: z
      .string()
      .trim()
      .min(1, { error: "Motivo requerido" })
      .max(255, { error: "Motivo demasiado largo" }),
    openingTime: optionalTime("Hora de apertura"),
    closingTime: optionalTime("Hora de cierre"),
    isActive: z.boolean().default(true),
  })
  .superRefine((data, ctx) => {
    if (data.tipo === "HORARIO_MODIFICADO") {
      if (!data.openingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Hora de apertura requerida",
        });
      }
      if (!data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "Hora de cierre requerida",
        });
      }
      if (
        data.openingTime &&
        data.closingTime &&
        data.openingTime >= data.closingTime
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "La hora de cierre debe ser mayor a la apertura",
        });
      }
    } else {
      if (data.openingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["openingTime"],
          message: "Solo horario modificado puede incluir horas",
        });
      }
      if (data.closingTime) {
        ctx.addIssue({
          code: "custom",
          path: ["closingTime"],
          message: "Solo horario modificado puede incluir horas",
        });
      }
    }
  });

export type BulkExcepcionFormValues = z.input<typeof bulkExcepcionFormSchema>;