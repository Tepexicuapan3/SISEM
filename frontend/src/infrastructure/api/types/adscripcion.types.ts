/**
 * P-03 · Adscripción a consultorio familiar (backend: /api/v1/adscripcion/...).
 * Contrato espejo de backend/apps/recepcion/views/adscripcion_views.py.
 */

export type EstadoAdscripcion =
  | "VIGENTE"
  | "SIN_ADSCRIPCION"
  | "NO_COINCIDE"
  | "CONSULTORIO_INACTIVO"
  | "CLINICA_SIN_CENTRO"
  | "P03_INACTIVO"
  | "NO_VIGENTE"
  | "SIN_DATO_EXPEDIENTE";

export type OrigenAdscripcion = "CHECKIN" | "CITA" | "MANUAL";

/** Lo que trae cada miembro en la búsqueda del expediente (patient-lookup). */
export interface AdscripcionResumen {
  estado: EstadoAdscripcion;
  requiereReasignar: boolean;
  claveClinicaSermed: string | null;
  idCentroSermed: number | null;
  /** Nombre del centro que SERMED le marca hoy (por la equivalencia). */
  centroSermed: string | null;
  idAdscripcion: number | null;
  idConsultorio: number | null;
  consultorio: string | null;
  numeroConsultorio: number | null;
  turno: string | null;
  idCentroAdscripcion: number | null;
  /** Centro de su consultorio actual; difiere de centroSermed si lo cambiaron de clínica. */
  centroAdscripcion: string | null;
  sinMedicoActivo: boolean;
  citasFuturas: number;
}

export interface Adscripcion {
  idAdscripcion: number;
  idPaciente: number;
  idCentroAtencion: number;
  centro: string;
  claveClinicaSermed: string;
  idConsultorio: number;
  consultorio: string;
  numeroConsultorio: number;
  idTurno: number;
  turno: string;
  estatus: "ACTIVA" | "CERRADA";
  origen: OrigenAdscripcion;
  fueSugerida: boolean;
  motivoCierre: string | null;
  observaciones: string | null;
  fechaInicio: string;
  fechaFin: string | null;
}

export interface CitaAdscripcion {
  idCita: number;
  folio: string;
  fechaHora: string;
  estatus: string;
  idConsultorio: number | null;
  consultorio: string | null;
  idMedico: number;
}

export interface AdscripcionPacienteResponse {
  idPaciente: number;
  estado: EstadoAdscripcion;
  requiereReasignar: boolean;
  claveClinicaSermed: string | null;
  idCentroSermed: number | null;
  adscripcion: Adscripcion | null;
  sinMedicoActivo: boolean;
  citasFuturas: CitaAdscripcion[];
  citasPorReagendar: number;
}

export interface OpcionConsultorio {
  consultorioId: number;
  consultorio: string;
  numero: number;
  turnoId: number;
  turno: string;
  carga: number;
  capacidadMaxima: number | null;
  esDeLaFamilia: boolean;
  sugerida: boolean;
}

export interface OpcionesAdscripcionResponse {
  estado: EstadoAdscripcion;
  idCentroSermed: number | null;
  opciones: OpcionConsultorio[];
}

export interface PrevisualizarAdscripcionRequest {
  idPaciente: number;
  consultorioId: number;
}

export interface PrevisualizarAdscripcionResponse {
  estado: EstadoAdscripcion;
  sinCambios: boolean;
  idAdscripcionActual: number | null;
  adscripcionActual: Adscripcion | null;
  citasACancelar: CitaAdscripcion[];
}

export interface AdscribirRequest {
  idPaciente: number;
  consultorioId: number;
  idAdscripcionEsperada: number | null;
  citasACancelar: number[];
  motivoCancelacionId?: number | null;
  origen: OrigenAdscripcion;
  fueSugerida: boolean;
  observaciones?: string | null;
}

export interface CitaAfectada {
  idCitaAfectada: number;
  idAdscripcion: number;
  /** Dónde reagendar: el consultorio de la adscripción que la canceló. */
  idPaciente: number;
  idConsultorioNuevo: number;
  consultorioNuevo: string;
  idCentroAtencion: number;
  estatus: "PENDIENTE" | "REAGENDADA" | "DESCARTADA";
  citaCancelada: CitaAdscripcion;
  idCitaNueva: number | null;
  motivoDescarte: string | null;
  fechaCreacion: string;
}

export interface AdscribirResponse {
  sinCambios: boolean;
  adscripcion: Adscripcion;
  citasCanceladas: CitaAdscripcion[];
  citasPorReagendar: CitaAfectada[];
}

// ── Asignación por familia (/adscripcion/familia) ───────────────────────────

/** Por qué no hay consultorio que ofrecer. */
export type MotivoSinOpciones = "SIN_CONSULTORIOS" | "SIN_MEDICO" | "TODOS_LLENOS";

/** Por qué un miembro no se puede asignar con su familia. */
export type RazonNoElegible =
  | "NO_VIGENTE"
  | "SIN_DATO_EXPEDIENTE"
  | "CLINICA_SIN_CENTRO"
  | "P03_INACTIVO"
  | "OTRA_CLINICA";

export interface MiembroFamiliaAdscripcion {
  noExp: string;
  /** PK_NUM de SERMED (0 = titular) o cd_provisional del recién nacido. */
  pkNum: number;
  idPaciente: number | null;
  nombre: string;
  parentesco: string | null;
  provisional: boolean;
  estado: EstadoAdscripcion | null;
  elegible: boolean;
  razon: RazonNoElegible | null;
  /** false si ya está en su consultorio: se mueve solo si recepción lo marca. */
  preseleccionado: boolean;
  idAdscripcionActual: number | null;
  idConsultorioActual: number | null;
  adscripcionActual: Adscripcion | null;
  /** Citas que se cancelarían con cada opción, por consultorioId. */
  citasACancelarPorConsultorio: Record<string, CitaAdscripcion[]>;
}

/** GET /adscripcion/familia: el núcleo listo para asignar (no escribe). */
export interface FamiliaAdscripcionResponse {
  noExp: string;
  idCentroAtencion: number | null;
  miembros: MiembroFamiliaAdscripcion[];
  opciones: OpcionConsultorio[];
  motivoSinOpciones: MotivoSinOpciones | null;
  /** El consultorio donde ya está la familia no se puede ofrecer. */
  familiaSeparada: boolean;
}

export interface AsignacionFamilia {
  pkNum: number;
  consultorioId: number;
  idAdscripcionEsperada: number | null;
  citasACancelar: number[];
  fueSugerida: boolean;
}

export interface AdscribirFamiliaRequest {
  noExp: string;
  asignaciones: AsignacionFamilia[];
  motivoCancelacionId: number | null;
  origen: OrigenAdscripcion;
}

export interface ResultadoAsignacionFamilia {
  pkNum: number;
  idPaciente: number;
  sinCambios: boolean;
  adscripcion: Adscripcion;
  citasCanceladas: CitaAdscripcion[];
}

/** POST /adscripcion/familia: todo o nada. */
export interface AdscribirFamiliaResponse {
  resultados: ResultadoAsignacionFamilia[];
}

export interface HistorialAdscripcionResponse {
  items: Adscripcion[];
}

export interface CitasPorReagendarParams {
  idPaciente?: number;
  centroId?: number;
}

export interface CitasPorReagendarResponse {
  items: CitaAfectada[];
}

// ── Configuración ────────────────────────────────────────────────────────────

export interface EquivalenciaClinica {
  idClinicaCentro: number;
  claveClinicaSermed: string;
  idCentroAtencion: number;
  centro: string;
  estaActivo: boolean;
}

export interface EquivalenciaClinicaCreateRequest {
  claveClinicaSermed: string;
  idCentroAtencion: number;
}

export interface EquivalenciaClinicaUpdateRequest {
  idCentroAtencion?: number;
  estaActivo?: boolean;
}

export interface ConsultorioFamiliar {
  idAdscripcionConsultorio: number;
  consultorioId: number;
  consultorio: string;
  numero: number;
  idCentroAtencion: number;
  turno: string;
  capacidadMaxima: number | null;
  estaActivo: boolean;
  carga: number | null;
}

export interface ConsultorioFamiliarCreateRequest {
  consultorioId: number;
  capacidadMaxima?: number | null;
}

export interface ConsultorioFamiliarUpdateRequest {
  capacidadMaxima?: number | null;
  estaActivo?: boolean;
}

export interface ListaResponse<T> {
  items: T[];
}

// ── Reporte de adscritos (admin) ─────────────────────────────────────────────

export type TipoDerechohabiente = "TITULAR" | "FAMILIAR";

export interface ConteoAdscritos {
  titulares: number;
  familiares: number;
  total: number;
}

export interface ResumenConsultorio extends ConteoAdscritos {
  consultorioId: number;
  consultorio: string;
  numero: number | null;
  turnoId: number;
  turno: string;
  capacidadMaxima: number | null;
  estaActivo: boolean;
  medicos: string[];
}

export interface ResumenCentro extends ConteoAdscritos {
  idCentroAtencion: number;
  centro: string;
  consultorios: ResumenConsultorio[];
}

export interface ResumenAdscripcionResponse {
  centros: ResumenCentro[];
  totales: ConteoAdscritos;
}

export interface Adscrito {
  idAdscripcion: number;
  idPaciente: number;
  noExp: string;
  nombre: string;
  tipo: TipoDerechohabiente;
  idCentroAtencion: number;
  centro: string;
  consultorioId: number;
  consultorio: string;
  numeroConsultorio: number | null;
  turnoId: number;
  turno: string;
  origen: OrigenAdscripcion;
  fechaInicio: string;
}

export interface AdscritosParams {
  centroId?: number;
  consultorioId?: number;
  turnoId?: number;
  tipo?: TipoDerechohabiente;
  q?: string;
  page?: number;
  pageSize?: number;
}

export interface AdscritosResponse {
  items: Adscrito[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}
