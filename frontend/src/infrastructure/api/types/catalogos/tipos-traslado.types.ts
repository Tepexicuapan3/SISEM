import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface TipoTrasladoListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface TipoTrasladoDetail extends TipoTrasladoListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateTipoTrasladoRequest {
  name: string;
  isActive?: boolean;
}

export interface UpdateTipoTrasladoRequest {
  name?: string;
  isActive?: boolean;
}

export type TipoTrasladoListResponse = ListResponse<TipoTrasladoListItem>;

export interface TipoTrasladoDetailResponse {
  tipoTraslado: TipoTrasladoDetail;
}

export interface CreateTipoTrasladoResponse {
  id: number;
  name: string;
}

export interface UpdateTipoTrasladoResponse {
  tipoTraslado: TipoTrasladoDetail;
}

export type DeleteTipoTrasladoResponse = SuccessResponse;

export interface TipoTrasladoListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
