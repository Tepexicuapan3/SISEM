/**
 * User Types - Pure TypeScript interfaces
 * Tipos para gestión de usuarios, roles asignados y overrides.
 *
 * @description Interfaces para CRUD de usuarios y sub-recursos (roles, overrides).
 * Todos los campos usan camelCase en inglés según el estándar de la API.
 */

import type { PaginationParams, ListResponse } from "@api/types/common.types";
import type { PermissionEffect } from "@api/types/permissions.types";
import type { CentroAtencionRef } from "@api/types/catalogos/centros-atencion.types";
import type { AreaClinicaRef } from "@api/types/catalogos/areas-clinicas.types";

export interface EscolaridadRef {
  id: number;
  name: string;
  isActive: boolean;
}

export interface EscuelaRef {
  id: number;
  name: string;
  code: string;
  isActive: boolean;
}

export interface TipoPersonalRef {
  id: number;
  name: string;
  isActive: boolean;
}

// =============================================================================
// OBJETOS ANIDADOS (Relaciones)
// =============================================================================

/**
 * Referencia a usuario (objeto anidado para auditoría).
 * Evita tener campos separados createdBy + createdByName.
 */
export interface UserRef {
  id: number;
  name: string;
}

export type CedulaTipo = "PROFESIONAL" | "ESPECIALIDAD" | "SUBESPECIALIDAD";

export interface CedulaItem {
  id?: number;
  numero: string;
  tipo: string;
  esPrincipal: boolean;
  orden: number;
}

export interface EmpleadoSermedResult {
  noExp: string;
  firstName: string;
  paternalName: string;
  maternalName: string;
  cdLaboral: string;
  cdClinica: string;
}

export interface EmpleadoSermedResponse {
  empleado: EmpleadoSermedResult;
}

// =============================================================================
// ENTIDADES PRINCIPALES
// =============================================================================

/**
 * Datos base para construir nombre completo.
 * Usado en utilidades compartidas de UI.
 */
export interface BaseUser {
  firstName: string;
  paternalName: string;
  maternalName: string;
}

/**
 * Usuario en listado (tabla administrativa).
 * Contiene solo datos necesarios para identificar, filtrar y mostrar en tabla.
 *
 * GET /api/v1/users
 */
export interface UserListItem {
  id: number;
  username: string;
  fullname: string;
  email: string;
  clinic: CentroAtencionRef | null;
  areaClinica: AreaClinicaRef | null;
  cdLaboral: string | null;
  telefono: string | null;
  sexo: "M" | "F" | null;
  fechaNac: string | null;
  escolaridad: EscolaridadRef | null;
  escuela: EscuelaRef | null;
  tipoPersonal: TipoPersonalRef | null;
  cedulas: CedulaItem[];
  primaryRole: string;
  isActive: boolean;
  termsAccepted?: boolean;
  mustChangePassword?: boolean;
}

/**
 * Usuario con información completa (página de detalle/edición).
 * Incluye datos personales separados, estado de cuenta y auditoría.
 *
 * GET /api/v1/users/:id
 */
export type TipoAdscripcionMedico = "CLINICA" | "HOSPITAL";
export type NivelEnfermeria = "GENERAL" | "ESPECIALISTA" | "JEFE_PISO";

export interface PerfilMedico {
  cedulaProfesional: string | null;
  cedulaEspecialidad: string | null;
  especialidad: { id: number; name: string } | null;
  tipoAdscripcion: TipoAdscripcionMedico | null;
}

export interface PerfilEnfermeria {
  cedulaEnfermeria: string | null;
  nivel: NivelEnfermeria | null;
  areaClinica: { id: number; name: string } | null;
}

export interface PerfilAdministrativo {
  puesto: string | null;
  areaAdministrativa: string | null;
}

export interface UserDetail extends UserListItem {
  // --- Datos personales (para edición) ---
  // telefono, sexo, fechaNac heredados de UserListItem
  firstName: string;
  paternalName: string;
  maternalName: string;

  // --- Datos SERMED / clínicos ---
  noExp: string | null;
  cdLaboral: string | null;
  areaClinica: AreaClinicaRef | null;
  cedulas: CedulaItem[];

  // --- Estado de cuenta ---
  termsAccepted: boolean;
  mustChangePassword: boolean;

  // --- Auditoría de conexión ---
  lastLoginAt: string | null;
  lastIp: string | null;

  // --- Auditoría de registro ---
  createdAt: string;
  createdBy: UserRef;
  updatedAt: string | null;
  updatedBy: UserRef | null;

  // --- Perfiles por tipo de personal (opcionales, no ligados 1:1 a tipoPersonal) ---
  perfilMedico: PerfilMedico | null;
  perfilEnfermeria: PerfilEnfermeria | null;
  perfilAdministrativo: PerfilAdministrativo | null;
}

/**
 * Rol asignado a un usuario.
 * Incluye metadatos de asignación.
 */
export interface UserRole {
  id: number;
  name: string;
  description: string;
  isPrimary: boolean;
  assignedAt: string;
  assignedBy: UserRef;
}

/**
 * Override de permiso para un usuario.
 * Permite ALLOW o DENY de permisos específicos.
 */
export interface UserOverride {
  id: number;
  permissionCode: string;
  permissionDescription: string;
  effect: PermissionEffect;
  expiresAt: string | null;
  isExpired: boolean;
  assignedAt: string;
  assignedBy: UserRef;
}

// =============================================================================
// CRUD REQUESTS
// =============================================================================

/**
 * Request para crear un nuevo usuario.
 * POST /api/v1/users
 */
export interface CreateUserRequest {
  username: string;
  firstName: string;
  paternalName: string;
  maternalName: string;
  email?: string;
  clinicId?: number | null;
  primaryRoleId: number;
  noExp?: string | null;
  cdLaboral?: string | null;
  telefono?: string | null;
  sexo?: "M" | "F" | null;
  fechaNac?: string | null;
  areaClinicaId?: number | null;
  escolaridadId?: number | null;
  escuelaId?: number | null;
  tipoPersonalId?: number | null;
  cedulas?: Omit<CedulaItem, "orden">[];
}

/**
 * Request para actualizar un usuario existente.
 * PATCH /api/v1/users/:id
 */
export interface UpdateUserRequest {
  firstName?: string;
  paternalName?: string;
  maternalName?: string;
  email?: string;
  clinicId?: number | null;
  noExp?: string | null;
  cdLaboral?: string | null;
  telefono?: string | null;
  sexo?: "M" | "F" | null;
  fechaNac?: string | null;
  areaClinicaId?: number | null;
  escolaridadId?: number | null;
  escuelaId?: number | null;
  tipoPersonalId?: number | null;
  cedulas?: Omit<CedulaItem, "orden">[];
  perfilMedico?: {
    cedulaProfesional?: string | null;
    cedulaEspecialidad?: string | null;
    idEspecialidad?: number | null;
    tipoAdscripcion?: TipoAdscripcionMedico | null;
  } | null;
  perfilEnfermeria?: {
    cedulaEnfermeria?: string | null;
    nivel?: NivelEnfermeria | null;
    idAreaClinica?: number | null;
  } | null;
  perfilAdministrativo?: {
    puesto?: string | null;
    areaAdministrativa?: string | null;
  } | null;
}

// =============================================================================
// CRUD RESPONSES
// =============================================================================

/**
 * Response al crear un usuario.
 * POST /api/v1/users
 */
export interface CreateUserResponse {
  id: number;
  username: string;
}

/**
 * Response al actualizar un usuario.
 * PATCH /api/v1/users/:id
 */
export interface UpdateUserResponse {
  user: UserDetail;
}

/**
 * Response al cambiar estado de un usuario (activar/desactivar).
 * PATCH /api/v1/users/:id/activate o /deactivate
 */
export interface UserStatusResponse {
  id: number;
  isActive: boolean;
}

/**
 * Response al restablecer la contraseña de un usuario.
 * La contraseña temporal viaja en texto plano SOLO en esta respuesta;
 * el frontend no debe persistirla mas alla del estado del modal de resultado
 * (nunca localStorage, nunca logs).
 * POST /api/v1/users/:id/reset-password
 */
export interface ResetUserPasswordResponse {
  temporaryPassword: string;
  mustChangePassword: boolean;
}

// =============================================================================
// LISTADOS
// =============================================================================

/**
 * Parámetros para listar usuarios.
 * GET /api/v1/users
 */
export interface UsersListParams extends PaginationParams {
  isActive?: boolean;
  roleId?: number;
  clinicId?: number;
  status?: "active" | "inactive" | "pending";
  tipoPersonalId?: number;
  /**
   * Filtro dedicado por No. Expediente SERMED (AND, independiente de `search`).
   * @endpoint GET /api/v1/users?noExp=...
   */
  noExp?: string;
}

/**
 * Response paginada de listado de usuarios.
 * GET /api/v1/users
 */
export type UsersListResponse = ListResponse<UserListItem>;

// =============================================================================
// NOTIFICACIONES
// =============================================================================

export interface NotifyUsersRequest {
  subject: string;
  message: string;
  category?: string;
  cdLaboral?: string;
  userId?: number | null;
  clinicId?: number | null;
}

export interface NotifyFailedItem {
  username: string;
  name: string;
  email: string;
}

export interface NotifyUsersResponse {
  sent: number;
  failed: NotifyFailedItem[];
}

export interface NotifyUsersPreviewResponse {
  count: number;
}

// =============================================================================
// DETALLE
// =============================================================================

/**
 * Response con detalle completo de un usuario.
 * GET /api/v1/users/:id
 */
export interface UserDetailResponse {
  user: UserDetail;
  roles: UserRole[];
  overrides: UserOverride[];
}

// =============================================================================
// SUB-RECURSO: ROLES
// =============================================================================

/**
 * Request para asignar roles a un usuario.
 * POST /api/v1/users/:id/roles
 */
export interface AssignRolesRequest {
  roleIds: number[];
}

/**
 * Response al asignar roles.
 * POST /api/v1/users/:id/roles
 */
export interface AssignRolesResponse {
  userId: number;
  roles: UserRole[];
}

/**
 * Request para establecer rol primario.
 * PUT /api/v1/users/:id/roles/primary
 */
export interface SetPrimaryRoleRequest {
  roleId: number;
}

/**
 * Response al establecer rol primario.
 * PUT /api/v1/users/:id/roles/primary
 */
export interface SetPrimaryRoleResponse {
  userId: number;
  roles: UserRole[];
}

/**
 * Response al revocar un rol.
 * DELETE /api/v1/users/:id/roles/:roleId
 */
export interface RevokeRoleResponse {
  userId: number;
  roles: UserRole[];
}

// =============================================================================
// IMPORTACION MASIVA (EXCEL)
// =============================================================================

/**
 * Datos normalizados de una fila del Excel de importacion.
 * Columnas de origen (en este orden exacto):
 * Usuario | Nombre(s) | Apellido Paterno | Apellido Materno | Correo |
 * No. Expediente SERMED | Rol | Tipo de Personal | Estado
 */
export interface UserImportRowData {
  username: string;
  firstName: string;
  paternalName: string;
  maternalName: string;
  email: string | null;
  noExp: string | null;
  roleName: string;
  roleId: number | null;
  tipoPersonalName: string;
  tipoPersonalId: number | null;
  estado: "Activo" | "Dado de baja";
  isActive: boolean;
}

/**
 * Fila procesada de la importacion (valida o con errores).
 */
export interface UserImportRow {
  row: number;
  data: UserImportRowData;
  errors: string[];
}

/**
 * Usuario cuya credencial de alta no se pudo enviar por correo durante el
 * confirm (el usuario SI se creo -- solo el email fallo y hay que reenviar
 * las credenciales manualmente).
 */
export interface UserImportEmailFailure {
  username: string;
  email: string;
}

/**
 * Response de preview/confirm de importacion masiva.
 * POST /api/v1/users/import/preview
 * POST /api/v1/users/import/confirm
 *
 * `emailFailures` solo viene poblado en la respuesta de confirm (preview
 * nunca envia correos).
 */
export interface UserImportResult {
  totalRecords: number;
  totalErrores: number;
  inserted: number;
  rows: UserImportRow[];
  emailFailures?: UserImportEmailFailure[];
}

// =============================================================================
// SUB-RECURSO: OVERRIDES
// =============================================================================

/**
 * Request para agregar un override de permiso.
 * POST /api/v1/users/:id/overrides
 */
export interface AddUserOverrideRequest {
  permissionCode: string;
  effect: PermissionEffect;
  expiresAt?: string;
}

/**
 * Response al agregar un override.
 * POST /api/v1/users/:id/overrides
 */
export interface AddUserOverrideResponse {
  userId: number;
  overrides: UserOverride[];
}

/**
 * Response al eliminar un override.
 * DELETE /api/v1/users/:id/overrides/:code
 */
export interface RemoveUserOverrideResponse {
  userId: number;
  overrides: UserOverride[];
}
