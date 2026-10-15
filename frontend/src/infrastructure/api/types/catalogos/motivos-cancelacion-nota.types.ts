import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface MotivoCancelacionNotaListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface MotivoCancelacionNotaDetail extends MotivoCancelacionNotaListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateMotivoCancelacionNotaRequest {
  name: string;
  isActive?: boolean;
}

export interface UpdateMotivoCancelacionNotaRequest {
  name?: string;
  isActive?: boolean;
}

export type MotivoCancelacionNotaListResponse = ListResponse<MotivoCancelacionNotaListItem>;

export interface MotivoCancelacionNotaDetailResponse {
  motivoCancelacionNota: MotivoCancelacionNotaDetail;
}

export interface CreateMotivoCancelacionNotaResponse {
  id: number;
  name: string;
}

export interface UpdateMotivoCancelacionNotaResponse {
  motivoCancelacionNota: MotivoCancelacionNotaDetail;
}

export type DeleteMotivoCancelacionNotaResponse = SuccessResponse;

export interface MotivoCancelacionNotaListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
