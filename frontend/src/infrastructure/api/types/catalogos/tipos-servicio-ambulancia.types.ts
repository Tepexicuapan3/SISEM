import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface TipoServicioAmbulanciaListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface TipoServicioAmbulanciaDetail extends TipoServicioAmbulanciaListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateTipoServicioAmbulanciaRequest {
  name: string;
  isActive?: boolean;
}

export interface UpdateTipoServicioAmbulanciaRequest {
  name?: string;
  isActive?: boolean;
}

export type TipoServicioAmbulanciaListResponse = ListResponse<TipoServicioAmbulanciaListItem>;

export interface TipoServicioAmbulanciaDetailResponse {
  tipoServicioAmbulancia: TipoServicioAmbulanciaDetail;
}

export interface CreateTipoServicioAmbulanciaResponse {
  id: number;
  name: string;
}

export interface UpdateTipoServicioAmbulanciaResponse {
  tipoServicioAmbulancia: TipoServicioAmbulanciaDetail;
}

export type DeleteTipoServicioAmbulanciaResponse = SuccessResponse;

export interface TipoServicioAmbulanciaListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
