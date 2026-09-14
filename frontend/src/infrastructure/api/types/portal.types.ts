/**
 * Tipos del Portal de Citas (autoservicio del paciente).
 * Contrato verificado contra backend/apps/portal_citas/{views,serializers}.py.
 */

export interface PortalIdentidadRequest {
  noExp: string;
  nombreCompleto: string;
  /** YYYY-MM-DD */
  fechaNacimiento: string;
}

export interface PortalIniciarSesionResponse {
  requiereCorreo: boolean;
  /** Solo presente cuando requiereCorreo=false (ya se mandó el OTP). */
  correoEnmascarado?: string;
}

export interface PortalCapturarCorreoRequest extends PortalIdentidadRequest {
  correo: string;
}

export interface PortalCapturarCorreoResponse {
  correoEnmascarado: string;
}

export interface PortalVerificarCodigoRequest extends PortalIdentidadRequest {
  codigo: string;
}

export interface PortalVerificarCodigoResponse {
  accessToken: string;
  tokenType: "Bearer";
  /** ISO 8601 */
  expiraEn: string;
}

export interface PortalNucleoMiembro {
  miembroId: string;
  nombreVisible: string;
  esMenor: boolean;
}

export interface PortalNucleoResponse {
  nucleo: PortalNucleoMiembro[];
}

export type PortalEstatusCita =
  | "agendada"
  | "confirmada"
  | "atendida"
  | "cancelada"
  | "no_asistio";

export interface PortalCitaListItem {
  folio: string;
  /** ISO 8601 */
  fechaHora: string;
  consultorioNombre: string | null;
  servicioTipo: string;
  estatus: PortalEstatusCita;
  paraQuien: string | null;
  cancelable: boolean;
}

export interface PortalCitasListResponse {
  citas: PortalCitaListItem[];
}

export interface PortalCentro {
  centroId: number;
  nombre: string | null;
}

export interface PortalCentrosResponse {
  centros: PortalCentro[];
}

export interface PortalConsultorio {
  consultorioId: number;
  nombre: string;
  numero: string | number;
  centroId: number | null;
  centroNombre: string | null;
}

export interface PortalConsultoriosResponse {
  consultorios: PortalConsultorio[];
}

export interface PortalDisponibilidadDia {
  fecha: string;
  slotsDisponibles: number;
}

export interface PortalDisponibilidadMensualResponse {
  consultorioId: number;
  anio: number;
  mes: number;
  dias: PortalDisponibilidadDia[];
}

export interface PortalSlot {
  slotId: number;
  /** YYYY-MM-DD */
  fecha: string;
  /** HH:MM */
  hora: string;
  consultorioNombre: string | null;
  especialidadPrincipal: string | null;
  estado: "disponible" | "ocupado";
}

export interface PortalSlotsResponse {
  slots: PortalSlot[];
}

export interface PortalReservarCitaRequest {
  miembroId: string;
  slotId: number;
  motivo?: string;
}

export interface PortalReservarCitaResponse {
  folio: string;
  /** ISO 8601 */
  fechaHora: string;
  consultorioNombre: string | null;
  servicioTipo: string;
}

export interface PortalCancelarCitaRequest {
  motivo?: string;
}

export interface PortalCancelarCitaResponse {
  folio: string;
  estatus: PortalEstatusCita;
}
