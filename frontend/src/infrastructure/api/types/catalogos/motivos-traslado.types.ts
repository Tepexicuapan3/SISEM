import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface MotivoTrasladoListItem {
  id: number;
  name: string;
  requiresNotes: boolean;
  isActive: boolean;
}

export interface MotivoTrasladoDetail extends MotivoTrasladoListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateMotivoTrasladoRequest {
  name: string;
  requiresNotes?: boolean;
  isActive?: boolean;
}

export interface UpdateMotivoTrasladoRequest {
  name?: string;
  requiresNotes?: boolean;
  isActive?: boolean;
}

export type MotivoTrasladoListResponse = ListResponse<MotivoTrasladoListItem>;

export interface MotivoTrasladoDetailResponse {
  motivoTraslado: MotivoTrasladoDetail;
}

export interface CreateMotivoTrasladoResponse {
  id: number;
  name: string;
}

export interface UpdateMotivoTrasladoResponse {
  motivoTraslado: MotivoTrasladoDetail;
}

export type DeleteMotivoTrasladoResponse = SuccessResponse;

export interface MotivoTrasladoListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
