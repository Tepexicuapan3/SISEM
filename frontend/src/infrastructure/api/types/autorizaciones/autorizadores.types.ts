import type { ListResponse, PaginationParams } from "@api/types/common.types";

/**
 * Autorizadores medicos - contrato alineado al backend (apps/autorizaciones):
 * - GET    /autorizadores/                       listado con filtros
 * - POST   /autorizadores/                       alta
 * - GET    /autorizadores/:id/                   detalle
 * - PATCH  /autorizadores/:id/                   edicion (exige version)
 * - POST   /autorizadores/:id/suspender|reactivar|baja|renovar/
 * - GET    /autorizadores/:id/historial/
 * - GET    /autorizadores/usuarios-elegibles/
 * - GET    /autorizaciones/catalogos/
 *
 * Errores de dominio (code): USER_INVALID, CEDULA_REQUIRED, INVALID_VALIDITY,
 * SCOPE_REQUIRED, VALIDATION_ERROR, REASON_REQUIRED (400); SELF_ADMIN_NOT_ALLOWED,
 * GLOBAL_PERMISSION_REQUIRED (403); AUTHORIZER_NOT_FOUND (404); AUTHORIZER_EXISTS,
 * STALE_VERSION, AUTHORIZER_INACTIVE, INVALID_STATUS_TRANSITION (409).
 */

export type ClaveTipoAutorizacion = "LAB" | "GAB" | "REC" | "CNO";
export type TipoCentroAlcance = "CLINICA" | "HOSPITAL" | "INSTITUTO";
export type EstatusAutorizador = "ACTIVO" | "SUSPENDIDO" | "INACTIVO";
export type EstadoVigencia = "PENDIENTE_INICIO" | "VIGENTE" | "POR_VENCER" | "VENCIDO";
export type AmbitoMotivo = "RECHAZO" | "SUSPENSION" | "BAJA" | "CANCELACION";

export interface ReferenciaUsuario {
  id: number;
  name: string;
}

export interface CedulaProfesional {
  numero: string;
  tipo: string;
  esPrincipal: boolean;
}

export interface MotivoResumen {
  id: number;
  clave: string;
  descripcion: string;
}

export interface AlcanceAutorizador {
  centros: { id: number; nombre: string; clues: string }[];
  tiposCentro: TipoCentroAlcance[];
  global: boolean;
}

export interface TipoAsignado {
  id: number;
  clave: ClaveTipoAutorizacion;
  nombre: string;
  fechaInicioVigencia: string | null;
  fechaFinVigencia: string | null;
  alcance: AlcanceAutorizador;
}

export interface AutorizadorItem {
  id: number;
  usuario: {
    id: number;
    usuario: string;
    nombreCompleto: string;
    cedulas: CedulaProfesional[];
  };
  cargo: string | null;
  numeroOficio: string | null;
  estatus: EstatusAutorizador;
  /** Calculado por el backend al momento de la consulta. */
  estadoVigencia: EstadoVigencia;
  /** YYYY-MM-DD */
  fechaInicioVigencia: string;
  /** YYYY-MM-DD */
  fechaFinVigencia: string;
  motivoEstatus: MotivoResumen | null;
  descripcionMotivoEstatus: string | null;
  fechaFinSuspension: string | null;
  tipos: TipoAsignado[];
  version: number;
  creadoPor: ReferenciaUsuario | null;
  fechaCreacion: string | null;
  modificadoPor: ReferenciaUsuario | null;
  fechaModificacion: string | null;
  fechaBaja: string | null;
}

export interface MovimientoAutorizador {
  id: number;
  tipoMovimiento:
    | "ALTA"
    | "EDICION"
    | "RENOVACION"
    | "SUSPENSION"
    | "REACTIVACION"
    | "BAJA"
    | "ALTA_TIPO"
    | "BAJA_TIPO"
    | "ALTA_CENTRO"
    | "BAJA_CENTRO"
    | "VENCIMIENTO";
  motivo: MotivoResumen | null;
  descripcionMotivo: string | null;
  datosAnteriores: Record<string, unknown> | null;
  datosNuevos: Record<string, unknown> | null;
  responsable: ReferenciaUsuario | null;
  fechaMovimiento: string;
}

export interface UsuarioElegible {
  id: number;
  usuario: string;
  nombreCompleto: string;
  tieneCedula: boolean;
}

export interface TipoAutorizacionCatalogo {
  id: number;
  clave: ClaveTipoAutorizacion;
  nombre: string;
  requiereCedula: boolean;
  modalidadPredeterminada: string;
}

export interface MotivoCatalogo {
  id: number;
  ambito: AmbitoMotivo;
  clave: string;
  descripcion: string;
  requiereDescripcionLibre: boolean;
}

// =============================================================================
// REQUESTS
// =============================================================================

export interface AlcanceRequest {
  centros: number[];
  tiposCentro: TipoCentroAlcance[];
  global: boolean;
}

export interface TipoAsignadoRequest {
  claveTipo: ClaveTipoAutorizacion;
  alcance: AlcanceRequest;
}

export interface AutorizadorAltaRequest {
  usuarioId: number;
  cargo: string | null;
  numeroOficio: string | null;
  fechaInicioVigencia: string;
  fechaFinVigencia: string;
  tipos: TipoAsignadoRequest[];
}

export interface AutorizadorEdicionRequest {
  cargo: string | null;
  numeroOficio: string | null;
  tipos: TipoAsignadoRequest[];
  version: number;
}

export interface CambioEstatusRequest {
  motivoId: number | null;
  descripcionMotivo: string | null;
  fechaFinSuspension?: string | null;
  version: number;
}

export interface RenovacionRequest {
  fechaFinVigencia: string;
  version: number;
}

export interface AutorizadoresListParams extends PaginationParams {
  search?: string;
  usuarioId?: number;
  tipo?: ClaveTipoAutorizacion;
  centroId?: number;
  estatus?: EstatusAutorizador;
  vigencia?: EstadoVigencia;
  fechaInicioDesde?: string;
  fechaFinHasta?: string;
}

// =============================================================================
// RESPONSES
// =============================================================================

export type AutorizadoresListResponse = ListResponse<AutorizadorItem>;

export interface AutorizadorDetailResponse {
  autorizador: AutorizadorItem;
}

export interface HistorialAutorizadorResponse {
  items: MovimientoAutorizador[];
}

export interface UsuariosElegiblesResponse {
  items: UsuarioElegible[];
}

export interface CatalogosAutorizacionResponse {
  tipos: TipoAutorizacionCatalogo[];
  motivos: MotivoCatalogo[];
}
