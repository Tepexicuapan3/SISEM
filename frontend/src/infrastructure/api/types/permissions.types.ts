/**
 * Permissions Types - Pure TypeScript interfaces
 * Tipos para catálogo de permisos del sistema.
 *
 * @description Interfaces para listar y mostrar permisos disponibles.
 * Los permisos son de solo lectura (no CRUD) y se ordenan por UI usando
 * la estructura del código "GRUPO:MODULO:SUBMODULO:ACCION".
 * Todos los campos usan camelCase en inglés según el estándar de la API.
 */

// =============================================================================
// TIPOS COMUNES
// =============================================================================

/**
 * Efecto de un permiso override: permitir o denegar.
 * Usado en overrides de usuarios para modificar permisos heredados de roles.
 */
export type PermissionEffect = "ALLOW" | "DENY";

// =============================================================================
// ENTIDADES
// =============================================================================

/**
 * Permiso del sistema (estructura completa).
 * Representa un permiso en el catálogo.
 *
 * Los permisos se ordenan en la UI usando la estructura del código:
 * "GRUPO:MODULO:SUBMODULO:ACCION" (ej: "clinico:expedientes:create", "admin:gestion:usuarios:read")
 */
export interface Permission {
  id: number;
  code: string; // (ej: "GRUPO:MODULO:SUBMODULO:ACCION")
  description: string;
  isSystem: boolean;
  /** Dependencias directas (codigos) que el backend exige junto con este permiso. Ausente en backends viejos. */
  dependsOn?: string[];
}

// =============================================================================
// RESPONSES
// =============================================================================

/**
 * Response del catálogo de permisos.
 * GET /api/v1/permissions
 */
export interface PermissionCatalogResponse {
  items: Permission[];
  total: number;
}

/**
 * Payload para crear un permiso nuevo.
 * POST /api/v1/permisos
 *
 * code debe seguir el formato "modulo:submodulo:accion" (minusculas,
 * numeros y guion bajo, separados por ":") — el backend lo valida igual.
 */
export interface CreatePermissionRequest {
  code: string;
  name: string;
}

export interface CreatePermissionResponse {
  id: number;
  name: string;
}
