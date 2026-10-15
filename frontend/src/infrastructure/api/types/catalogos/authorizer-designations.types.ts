import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";

/**
 * Designacion de autorizadores - contrato alineado al backend:
 * - GET    /authorizer-designations/
 * - POST   /authorizer-designations/
 * - GET    /authorizer-designations/:id/
 * - PUT    /authorizer-designations/:id/
 * - DELETE /authorizer-designations/:id/   (baja logica)
 *
 * Errores de dominio (code): DESIGNATION_NOT_FOUND (404), DESIGNATION_EXISTS (409),
 * GLOBAL_PERMISSION_REQUIRED (403), GLOBAL_REQUIRES_END_DATE (400), VALIDATION_ERROR (400).
 */

export type CentroTipoDesignacion = "CLINICA" | "HOSPITAL" | "INSTITUTO";

// =============================================================================
// ENTIDADES
// =============================================================================

export interface DesignacionAlcance {
  centros: { id: number; name: string }[];
  tiposCentro: CentroTipoDesignacion[];
  global: boolean;
}

export interface DesignacionItem {
  id: number;
  userId: number;
  user: { id: number; username: string; name: string };
  tipoAutorizacionId: number;
  tipoAutorizacion: { id: number; name: string; code: string };
  cargo: string;
  /** YYYY-MM-DD */
  fechaInicio: string;
  /** YYYY-MM-DD | null (sin fin; obligatoria con alcance GLOBAL) */
  fechaFin: string | null;
  oficio: string | null;
  imgFirma: string | null;
  alcance: DesignacionAlcance;
  isActive: boolean;
  /** Calculado por el backend: activa y dentro de vigencia hoy. */
  vigente: boolean;
  createdAt: string | null;
}

// =============================================================================
// REQUESTS
// =============================================================================

export interface DesignacionAlcanceRequest {
  centros: number[];
  tiposCentro: CentroTipoDesignacion[];
  /** El backend rechaza (400) `global` combinado con centros/tiposCentro. */
  global: boolean;
}

export interface DesignacionWriteRequest {
  userId: number;
  tipoAutorizacionId: number;
  cargo: string;
  fechaInicio: string;
  fechaFin?: string | null;
  oficio?: string | null;
  alcance: DesignacionAlcanceRequest;
}

// =============================================================================
// RESPONSES
// =============================================================================

export type DesignacionesListResponse = ListResponse<DesignacionItem>;

export interface DesignacionDetailResponse {
  designation: DesignacionItem;
}

export type DeleteDesignacionResponse = SuccessResponse;

// =============================================================================
// PARAMS
// =============================================================================

export interface DesignacionesListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  tipoAutorizacionId?: number;
  sortBy?: "createdAt" | "cargo" | "fechaInicio" | "fechaFin" | "isActive";
  sortOrder?: "asc" | "desc";
}
