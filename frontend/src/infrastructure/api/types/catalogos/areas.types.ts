/**
 * Areas Types - Pure TypeScript interfaces
 * Tipos para gestion completa de areas del Metro CDMX.
 */

import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface AreaListItem {
  id: number;
  name: string;
  code: string;
  isActive: boolean;
}

export interface AreaDetail extends AreaListItem {
  tipoArea: { id: number; name: string } | null;
  createdAt: string;
  createdBy: UserRef;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

// =============================================================================
// CRUD REQUESTS
// =============================================================================

export interface CreateAreaRequest {
  name: string;
  code: string;
  idTipoArea: number;
}

export interface UpdateAreaRequest {
  name?: string;
  code?: string;
  idTipoArea?: number;
  isActive?: boolean;
}

// =============================================================================
// CRUD RESPONSES
// =============================================================================

export type AreasListResponse = ListResponse<AreaListItem>;

export interface AreaDetailResponse {
  area: AreaDetail;
}

export interface CreateAreaResponse {
  id: number;
  name: string;
}

export interface UpdateAreaResponse {
  area: AreaDetail;
}

export type DeleteAreaResponse = SuccessResponse;

// =============================================================================
// PARAMS
// =============================================================================

export interface AreasListParams extends PaginationParams {
  isActive?: boolean;
}
