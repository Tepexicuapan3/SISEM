import * as z from "zod";

const requiredText = (label: string, maxLength = 120) =>
  z
    .string()
    .trim()
    .min(1, { error: `${label} requerido` })
    .max(maxLength, { error: `${label} demasiado largo` });

/**
 * `moduleKindSchema` -- distingue "carpeta" (`isSection=true`, contenedor
 * sin destino propio) de "acceso directo" (`isSection=false`, apunta a un
 * `MenuDestination` real). Es el campo que arma el Paso 1 del
 * `ModuleCreateWizard` -- de el depende que pasos siguientes se muestran
 * (una carpeta no pasa por `MenuDestinationSelect`).
 */
export const moduleKindSchema = z.enum(["folder", "shortcut"]);

/**
 * Paso 1 del wizard: tipo + titulo + icono. Comun a carpetas y accesos
 * directos -- ambos se muestran con icono en el arbol real (`ModuleTreeRow`,
 * sidebar), asi que el picker vive aca y no depende del paso de destino.
 *
 * `icon: null` es el caso explicito "sin elegir" -- el módulo cae al
 * default (`Circle`) via `resolveNavIcon`, mismo criterio que ya usa el
 * resto del sistema para un icono ausente/desconocido.
 */
export const moduleBasicsSchema = z.object({
  kind: moduleKindSchema,
  title: requiredText("Título"),
  icon: z.string().trim().min(1).nullable(),
});

/**
 * Paso 2 del wizard (solo `kind === "shortcut"`): destino elegido en
 * `MenuDestinationSelect`. `url`/`permissionCodes` viajan JUNTOS porque
 * el usuario NUNCA edita un codigo de permiso a mano -- se derivan los dos
 * de la MISMA seleccion (ver D3 del design: el backend igual revalida
 * `permissionCodes` contra `cat_permisos` + scope del actor, esto es solo
 * el paso de UI que arma el payload).
 *
 * `url: null` + `permissionCodes: []` es el caso "unmanaged" explicito:
 * un destino real que no declara permisos (ej. `/dashboard`) -- se
 * permite, la UI lo advierte, nunca se bloquea ni se inventa un codigo.
 */
export const moduleDestinationSchema = z.object({
  url: z.string().trim().min(1, { error: "Selecciona un destino" }).nullable(),
  permissionCodes: z.array(z.string()),
});

/**
 * Paso 3 del wizard: ubicacion en el arbol. `parentKey: null` = raiz.
 */
export const modulePlacementSchema = z.object({
  parentKey: z.string().trim().min(1).nullable(),
});

/**
 * Payload completo que arma `ModuleCreateWizard` al confirmar el paso 3 --
 * combina los 3 pasos en la forma que espera `useCreateModule`
 * (`CreateModuleRequest`, sin `clave`: la deriva el servidor).
 *
 * `superRefine` exige `url` SOLO cuando `kind === "shortcut"` -- una
 * carpeta (`kind === "folder"`) no tiene destino, asi que el paso 2 del
 * wizard se saltea entero para ese tipo y el campo queda `null`.
 */
export const createModuleFormSchema = moduleBasicsSchema
  .extend(moduleDestinationSchema.shape)
  .extend(modulePlacementSchema.shape)
  .superRefine((data, ctx) => {
    if (data.kind === "shortcut" && !data.url) {
      ctx.addIssue({
        code: "custom",
        message: "Selecciona un destino",
        path: ["url"],
      });
    }
  });
export type CreateModuleFormValues = z.infer<typeof createModuleFormSchema>;
