import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface TipoCirugiaListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface TipoCirugiaDetail extends TipoCirugiaListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateTipoCirugiaRequest {
  name: string;
  isActive?: boolean;
}

export interface UpdateTipoCirugiaRequest {
  name?: string;
  isActive?: boolean;
}

export type TipoCirugiaListResponse = ListResponse<TipoCirugiaListItem>;

export interface TipoCirugiaDetailResponse {
  tipoCirugia: TipoCirugiaDetail;
}

export interface CreateTipoCirugiaResponse {
  id: number;
  name: string;
}

export interface UpdateTipoCirugiaResponse {
  tipoCirugia: TipoCirugiaDetail;
}

export type DeleteTipoCirugiaResponse = SuccessResponse;

export interface TipoCirugiaListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
