import * as z from "zod";

const requiredText = (label: string) =>
  z
    .string({ error: `${label} requerido` })
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(120, { error: `${label} demasiado largo` });

const optionalText = z
  .string({ error: "Texto invalido" })
  .trim()
  .max(120, { error: "Texto demasiado largo" });

const emailSchema = z
  .string({ error: "Correo invalido" })
  .trim()
  .email({ error: "Correo invalido" });

// Correo opcional: si el usuario no lo captura se omite (string vacio o
// ausente), pero si escribe algo se sigue validando el formato de email.
const optionalEmailSchema = emailSchema.optional().or(z.literal(""));

const optionalNumber = z.preprocess(
  (value) => {
    if (
      value === "" ||
      value === "none" ||
      value === 0 ||
      value === null ||
      value === undefined
    ) {
      return null;
    }

    if (typeof value === "string") {
      const parsed = Number(value);
      return Number.isNaN(parsed) ? null : parsed;
    }

    return value;
  },
  z
    .number({ error: "Selecciona un centro valido" })
    .int()
    .positive({ error: "Selecciona un centro valido" })
    .nullable()
    .default(null),
);

const requiredNumber = z
  .number({ error: "Selecciona un rol" })
  .int()
  .positive({ error: "Selecciona un rol" });

const cedulaSchema = z.object({
  id: z.number().int().positive().optional(),
  numero: z
    .string({ error: "Número de cédula requerido" })
    .trim()
    .min(1, { error: "Número de cédula requerido" })
    .max(30, { error: "Número de cédula demasiado largo" }),
  tipo: z
    .string({ error: "Tipo de cédula requerido" })
    .trim()
    .min(1, { error: "El tipo de cédula es requerido" })
    .max(80, { error: "El tipo es demasiado largo" }),
  esPrincipal: z.boolean().default(false),
});

export type CedulaFormItem = z.infer<typeof cedulaSchema>;

export const userDetailsSchema = z
  .object({
    firstName: requiredText("Nombre"),
    paternalName: requiredText("Apellido paterno"),
    maternalName: optionalText,
    email: optionalEmailSchema,
    clinicId: optionalNumber,
    noExp: z.string().trim().max(20).nullable().default(null),
    cdLaboral: z.string().trim().max(100).nullable().default(null),
    telefono: z.string().trim().max(20).nullable().default(null),
    sexo: z.enum(["M", "F", "O"]).nullable().default(null),
    fechaNac: z.string().nullable().default(null),
    areaClinicaId: optionalNumber,
    escolaridadId: optionalNumber,
    escuelaId: optionalNumber,
    tipoPersonalId: optionalNumber,
    cedulas: z
      .array(cedulaSchema)
      .max(3, { message: "Solo se permiten hasta 3 cédulas" })
      .default([]),
  })
  .refine(
    (data) => data.cedulas.filter((c) => c.esPrincipal).length <= 1,
    { message: "Solo puede haber una cédula principal", path: ["cedulas"] },
  );

export const createUserSchema = z
  .object({
    username: z
      .string({ error: "Usuario requerido" })
      .trim()
      .min(3, { error: "Usuario requerido" })
      .max(60, { error: "Usuario demasiado largo" }),
    firstName: requiredText("Nombre"),
    paternalName: requiredText("Apellido paterno"),
    maternalName: optionalText,
    email: optionalEmailSchema,
    clinicId: optionalNumber,
    primaryRoleId: requiredNumber,
    noExp: z.string().trim().max(20).nullable().default(null),
    cdLaboral: z.string().trim().max(100).nullable().default(null),
    telefono: z.string().trim().max(20).nullable().default(null),
    sexo: z.enum(["M", "F", "O"]).nullable().default(null),
    fechaNac: z.string().nullable().default(null),
    areaClinicaId: optionalNumber,
    escolaridadId: optionalNumber,
    escuelaId: optionalNumber,
    tipoPersonalId: optionalNumber,
    cedulas: z
      .array(cedulaSchema)
      .max(3, { message: "Solo se permiten hasta 3 cédulas" })
      .default([]),
  })
  .refine(
    (data) => data.cedulas.filter((c) => c.esPrincipal).length <= 1,
    { message: "Solo puede haber una cédula principal", path: ["cedulas"] },
  );

export type UserDetailsFormValues = z.infer<typeof userDetailsSchema>;
export type CreateUserFormValues = z.infer<typeof createUserSchema>;
