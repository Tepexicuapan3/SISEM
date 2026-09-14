import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

// =============================================================================
// ENTIDADES
// =============================================================================

export interface Cie9McListItem {
  id: number;
  name: string;
  code: string;
  isActive: boolean;
}

export interface Cie9McDetail extends Cie9McListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

// =============================================================================
// REQUESTS
// =============================================================================

export interface CreateCie9McRequest {
  name: string;
  code: string;
  isActive?: boolean;
}

export interface UpdateCie9McRequest {
  name?: string;
  code?: string;
  isActive?: boolean;
}

// =============================================================================
// RESPONSES
// =============================================================================

export type Cie9McListResponse = ListResponse<Cie9McListItem>;

export interface Cie9McDetailResponse {
  cie9Mc: Cie9McDetail;
}

export interface CreateCie9McResponse {
  id: number;
  name: string;
  code: string;
}

export interface UpdateCie9McResponse {
  cie9Mc: Cie9McDetail;
}

export type DeleteCie9McResponse = SuccessResponse;

// =============================================================================
// PARAMS
// =============================================================================

export interface Cie9McListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "code" | "isActive";
  sortOrder?: "asc" | "desc";
}
