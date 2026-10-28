import type { AmbitoMotivo } from "@api/types/autorizaciones/configuracion.types";

export const configuracionKeys = {
  all: ["admin", "autorizaciones-config"] as const,
  tipos: () => [...configuracionKeys.all, "tipos"] as const,
  reglas: () => [...configuracionKeys.all, "reglas"] as const,
  motivos: (ambito?: AmbitoMotivo) => [...configuracionKeys.all, "motivos", ambito ?? "todos"] as const,
};
