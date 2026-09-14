import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export interface DestinoAmbulanciaListItem {
  id: number;
  name: string;
  isActive: boolean;
}

export interface DestinoAmbulanciaDetail extends DestinoAmbulanciaListItem {
  street: string | null;
  zipCode: string | null;
  neighborhood: string | null;
  borough: string | null;
  phone: string | null;
  reference: string | null;
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateDestinoAmbulanciaRequest {
  name: string;
  street?: string;
  zipCode?: string;
  neighborhood?: string;
  borough?: string;
  phone?: string;
  reference?: string;
  isActive?: boolean;
}

export interface UpdateDestinoAmbulanciaRequest {
  name?: string;
  street?: string;
  zipCode?: string;
  neighborhood?: string;
  borough?: string;
  phone?: string;
  reference?: string;
  isActive?: boolean;
}

export type DestinoAmbulanciaListResponse = ListResponse<DestinoAmbulanciaListItem>;

export interface DestinoAmbulanciaDetailResponse {
  destinoAmbulancia: DestinoAmbulanciaDetail;
}

export interface CreateDestinoAmbulanciaResponse {
  id: number;
  name: string;
}

export interface UpdateDestinoAmbulanciaResponse {
  destinoAmbulancia: DestinoAmbulanciaDetail;
}

export type DeleteDestinoAmbulanciaResponse = SuccessResponse;

export interface DestinoAmbulanciaListParams extends PaginationParams {
  search?: string;
  isActive?: boolean;
  sortBy?: "name" | "isActive";
  sortOrder?: "asc" | "desc";
}
