import type { PermissionRequirement } from "@/domains/auth-access/types/permission-dependencies";

/**
 * P-03 · Permisos atómicos (espejo de backend/apps/authentication/services/
 * permission_dependencies.py). En el front son solo UX: el backend decide.
 */
export const ADSCRIPCION_CAPABILITY = {
  READ: "recepcion:consultorio_familiar:read",
  WRITE: "recepcion:consultorio_familiar:write",
  EXCEPCION: "recepcion:consultorio_familiar:excepcion",
  CONFIG: "admin:catalogos:consultorio_familiar:config",
} as const;

export const ADSCRIPCION_REQUIREMENT: Record<keyof typeof ADSCRIPCION_CAPABILITY, PermissionRequirement> = {
  READ: { allOf: [ADSCRIPCION_CAPABILITY.READ] },
  WRITE: { allOf: [ADSCRIPCION_CAPABILITY.WRITE] },
  EXCEPCION: { allOf: [ADSCRIPCION_CAPABILITY.EXCEPCION] },
  CONFIG: { allOf: [ADSCRIPCION_CAPABILITY.CONFIG] },
};
