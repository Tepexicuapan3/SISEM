import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface MotivoBajaPadronListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface MotivoBajaPadronDetail extends MotivoBajaPadronListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateMotivoBajaPadronRequest {
  name: string;
  isActive?: boolean;
}

export interface UpdateMotivoBajaPadronRequest {
  name?: string;
  isActive?: boolean;
}

export type MotivoBajaPadronListResponse = ListResponse<MotivoBajaPadronListItem>;

export interface MotivoBajaPadronDetailResponse {
  motivoBajaPadron: MotivoBajaPadronDetail;
}

export interface CreateMotivoBajaPadronResponse {
  id: number;
  name: string;
}

export interface UpdateMotivoBajaPadronResponse {
  motivoBajaPadron: MotivoBajaPadronDetail;
}

export type DeleteMotivoBajaPadronResponse = SuccessResponse;

export interface MotivoBajaPadronListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
