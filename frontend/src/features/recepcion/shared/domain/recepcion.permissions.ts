import type { PermissionRequirement } from "@/domains/auth-access/types/permission-dependencies";

export const RECEPCION_WRITE_PERMISSIONS = [
  "recepcion:fichas:medicina_general:create",
  "recepcion:fichas:especialidad:create",
  "recepcion:fichas:urgencias:create",
] as const;

export const RECEPCION_QUEUE_READ_PERMISSIONS = [
  ...RECEPCION_WRITE_PERMISSIONS,
  "clinico:consultas:read",
  "clinico:somatometria:read",
] as const;

export const RECEPCION_WRITE_PERMISSION_REQUIREMENT = {
  anyOf: RECEPCION_WRITE_PERMISSIONS,
} as const satisfies PermissionRequirement;

export const RECEPCION_QUEUE_PERMISSION_REQUIREMENT = {
  anyOf: RECEPCION_QUEUE_READ_PERMISSIONS,
} as const satisfies PermissionRequirement;

export const CITAS_READ_PERMISSION  = "recepcion:citas:read"  as const;
export const CITAS_WRITE_PERMISSION = "recepcion:citas:write" as const;

export const CITAS_READ_PERMISSION_REQUIREMENT = {
  anyOf: [CITAS_READ_PERMISSION, CITAS_WRITE_PERMISSION],
} as const satisfies PermissionRequirement;

// Change `incapacidad-medica-recepcion-frontend`: permiso de SOLO LECTURA
// para que Recepcion consulte el historial de incapacidades por no_exp.
// clinico:consultas:read se acepta como alternativa (medico) -- ver
// DOCTOR_OR_INCAPACIDAD_READ_PERMISSION_REQUIREMENT en el backend
// (consultation_usecase.py).
export const INCAPACIDAD_READ_PERMISSIONS = [
  "recepcion:incapacidad:read",
  "clinico:consultas:read",
] as const;

export const INCAPACIDAD_READ_PERMISSION_REQUIREMENT = {
  anyOf: INCAPACIDAD_READ_PERMISSIONS,
} as const satisfies PermissionRequirement;
