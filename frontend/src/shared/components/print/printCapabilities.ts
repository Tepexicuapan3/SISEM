import type { PrintableDocument } from "@api/resources/impresion.api";
import type { PermissionRequirement } from "@/domains/auth-access/types/permission-dependencies";

/**
 * Capability del backend por documento + fallback local (espejo de
 * CAPABILITY_REQUIREMENTS en permission_dependencies.py) para cuando la
 * proyeccion de capabilities aun no esta cargada.
 */
export const PRINT_CAPABILITIES: Record<
  PrintableDocument,
  { key: string; fallback: PermissionRequirement }
> = {
  ficha: {
    key: "documentos.ficha.imprimir",
    fallback: {
      anyOf: [
        "recepcion:fichas:medicina_general:create",
        "recepcion:fichas:especialidad:create",
        "recepcion:fichas:urgencias:create",
        "clinico:consultas:read",
      ],
    },
  },
  receta: {
    key: "documentos.receta.imprimir",
    fallback: {
      anyOf: ["clinico:recetas:imprimir", "farmacia:recetas:dispensar"],
    },
  },
  nota: {
    key: "documentos.nota.imprimir",
    fallback: { allOf: ["clinico:consultas:read"] },
  },
};
