import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface ClasificacionCirugiaListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface ClasificacionCirugiaDetail extends ClasificacionCirugiaListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateClasificacionCirugiaRequest {
  name: string;
  isActive?: boolean;
}

export interface UpdateClasificacionCirugiaRequest {
  name?: string;
  isActive?: boolean;
}

export type ClasificacionCirugiaListResponse = ListResponse<ClasificacionCirugiaListItem>;

export interface ClasificacionCirugiaDetailResponse {
  clasificacionCirugia: ClasificacionCirugiaDetail;
}

export interface CreateClasificacionCirugiaResponse {
  id: number;
  name: string;
}

export interface UpdateClasificacionCirugiaResponse {
  clasificacionCirugia: ClasificacionCirugiaDetail;
}

export type DeleteClasificacionCirugiaResponse = SuccessResponse;

export interface ClasificacionCirugiaListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
