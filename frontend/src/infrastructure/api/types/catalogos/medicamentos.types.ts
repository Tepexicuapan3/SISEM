import type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
} from "@api/types/common.types";
import type { UserRef } from "@api/types/users.types";

export type CuadroBasico = "BASICO" | "ESPECIAL" | "INSTITUCIONAL";

export interface MedicamentoListItem {
  id: number;
  /** Clave del Compendio Nacional de Insumos (opcional). */
  code: string | null;
  name: string;
  genericName: string | null;
  presentation: string | null;
  cuadroBasico: CuadroBasico;
  isControlled: boolean;
  maxQuantity: number | null;
  isActive: boolean;
}

export interface MedicamentoDetail extends MedicamentoListItem {
  createdAt: string;
  createdBy: UserRef | null;
  updatedAt: string | null;
  updatedBy: UserRef | null;
}

export interface CreateMedicamentoRequest {
  name: string;
  code: string | null;
  genericName: string | null;
  presentation: string | null;
  cuadroBasico: CuadroBasico;
  isControlled: boolean;
  maxQuantity: number | null;
  isActive?: boolean;
}

export type UpdateMedicamentoRequest = Partial<CreateMedicamentoRequest>;

export interface CreateMedicamentoResponse {
  id: number;
  name: string;
}

export interface MedicamentoDetailResponse {
  medication: MedicamentoDetail;
}

export type UpdateMedicamentoResponse = MedicamentoDetailResponse;

export type DeleteMedicamentoResponse = SuccessResponse;

export type MedicamentosListResponse = ListResponse<MedicamentoListItem>;

export interface MedicamentosListParams extends PaginationParams {
  /** Busca por nombre, generico o clave. */
  search?: string;
  isActive?: boolean;
  cuadroBasico?: CuadroBasico;
}
