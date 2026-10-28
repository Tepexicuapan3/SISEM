// Contrato de /api/v1/autorizaciones/configuracion/ (tipos, reglas por centro, motivos).

export type Modalidad = "PRIMERO_VALIDO" | "MULTIPLE";
export type AmbitoMotivo = "RECHAZO" | "SUSPENSION" | "BAJA" | "CANCELACION";

export interface TipoConfiguracion {
  id: number;
  clave: string;
  nombre: string;
  version: number;
  modalidadPredeterminada: Modalidad;
  aprobacionesRequeridas: number;
  rechazoResuelveSolicitud: boolean;
  permiteRechazo: boolean;
  horasVigenciaSolicitud: number;
  horasEscalamiento: number;
  requiereCedula: boolean;
}

export type TipoEdicionRequest = Omit<TipoConfiguracion, "id" | "clave" | "nombre">;

export interface ReglaCentro {
  id: number;
  tipoId: number;
  claveTipo: string;
  centroId: number;
  centroNombre: string;
  version: number;
  /** null = hereda el valor del tipo. */
  modalidad: Modalidad | null;
  aprobacionesRequeridas: number | null;
  horasVigenciaSolicitud: number | null;
}

export interface ReglaCentroValores {
  modalidad: Modalidad | null;
  aprobacionesRequeridas: number | null;
  horasVigenciaSolicitud: number | null;
}

export interface ReglaCentroAltaRequest extends ReglaCentroValores {
  tipoId: number;
  centroId: number;
}

export interface ReglaCentroEdicionRequest extends ReglaCentroValores {
  version: number;
}

export interface MotivoConfiguracion {
  id: number;
  ambito: AmbitoMotivo;
  clave: string;
  descripcion: string;
  requiereDescripcionLibre: boolean;
  activo: boolean;
  version: number;
}

export interface MotivoAltaRequest {
  ambito: AmbitoMotivo;
  clave: string;
  descripcion: string;
  requiereDescripcionLibre: boolean;
}

export interface MotivoEdicionRequest {
  version: number;
  descripcion?: string;
  requiereDescripcionLibre?: boolean;
  activo?: boolean;
}

export interface ListaResponse<T> {
  items: T[];
}
