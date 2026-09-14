import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface MotivoCancelacionCirugiaListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface MotivoCancelacionCirugiaDetail extends MotivoCancelacionCirugiaListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateMotivoCancelacionCirugiaRequest {
  name: string;
  isActive?: boolean;
}

export interface UpdateMotivoCancelacionCirugiaRequest {
  name?: string;
  isActive?: boolean;
}

export type MotivoCancelacionCirugiaListResponse = ListResponse<MotivoCancelacionCirugiaListItem>;

export interface MotivoCancelacionCirugiaDetailResponse {
  motivoCancelacionCirugia: MotivoCancelacionCirugiaDetail;
}

export interface CreateMotivoCancelacionCirugiaResponse {
  id: number;
  name: string;
}

export interface UpdateMotivoCancelacionCirugiaResponse {
  motivoCancelacionCirugia: MotivoCancelacionCirugiaDetail;
}

export type DeleteMotivoCancelacionCirugiaResponse = SuccessResponse;

export interface MotivoCancelacionCirugiaListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
