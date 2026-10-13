export type TipoMedico      = "CLINICA" | "HOSPITAL" | "AMBOS";
export type EstatusMedico   = "ACTIVO" | "VACACIONES" | "INCAPACIDAD" | "SUSPENDIDO" | "BAJA";
export type TipoAdscripcion = "DEFINITIVA" | "TEMPORAL";
export type TipoAsignacion  = "PERMANENTE" | "TEMPORAL";
export type CanalAtencion   = "PRESENCIAL" | "LINEA" | "AMBOS";
export type DiaSemana       = "LUNES" | "MARTES" | "MIERCOLES" | "JUEVES" | "VIERNES" | "SABADO" | "DOMINGO";
export type TipoExcepcion   = "VACACIONES" | "INCAPACIDAD" | "PERMISO" | "HORA_COMIDA" |
                              "CAPACITACION" | "AUSENCIA" | "SUSPENSION" | "CAMBIO_HORARIO";
export type MotivoCobertura = "VACACIONES" | "INCAPACIDAD" | "PERMISO" | "OTRO";

// ─── MÉDICO ──────────────────────────────────────────────────────────────────

export interface MedicoCedulaItem {
  id: number;
  numero: string;
  tipo: "PROFESIONAL" | "ESPECIALIDAD" | "SUBESPECIALIDAD";
  esPrincipal: boolean;
}

export interface MedicoEspecialidadItem {
  id: number;
  name: string;
  esPrincipal: boolean;
}

export interface MedicoCentroItem {
  id: number;
  centroId: number;
  centroNombre: string;
  centroDireccion: string | null;
  centroTelefono: string | null;
  tipoAdscripcion: TipoAdscripcion;
  fechaInicio: string;
  fechaFin: string | null;
}

export interface MedicoHorarioItem {
  id: number;
  diaSemana: DiaSemana;
  horaInicio: string;
  horaFin: string;
  intervaloCitaMin: number;
  canal: CanalAtencion;
}

export interface MedicoConsultorioItem {
  id: number;
  consultorioId: number;
  consultorioNumero: number;
  consultorioNombre: string;
  tipoAsignacion: TipoAsignacion;
  fechaInicio: string;
  fechaFin: string | null;
  isActive: boolean;
  horarios: MedicoHorarioItem[];
}

export interface MedicoEscuelaItem {
  id: number;
  code: string;
  name: string;
}

export interface MedicoConsultorioActivoItem {
  id: number;
  consultorioId: number;
  consultorioNumero: number;
  consultorioNombre: string;
  centroId: number;
  centroNombre: string;
}

export interface MedicoListItem {
  /** CatMedico.id = No. Médico. Es el único id válido para URLs y payloads de médico. */
  id: number;
  /** SyUsuario asociado; null en médicos sin usuario. NUNCA usarlo como id de médico. */
  usuarioId: number | null;
  tieneUsuario: boolean;
  username: string | null;
  nombreCompleto: string;
  nombre: string;
  paterno: string;
  materno: string;
  cedulaProfesional: string | null;
  email: string | null;
  telefono: string | null;
  direccion: string | null;
  sexo: "M" | "F" | "O" | null;
  fechaNac: string | null;
  isActive: boolean;
  tipoMedico: TipoMedico;
  servicio: string | null;
  estatusMedico: EstatusMedico;
  escuela: MedicoEscuelaItem | null;
  cedulas: MedicoCedulaItem[];
  especialidades: MedicoEspecialidadItem[];
  centros: MedicoCentroItem[];
  consultoriosActivos: MedicoConsultorioActivoItem[];
  createdAt: string | null;
}

export interface MedicoDetail extends MedicoListItem {
  observaciones: string | null;
  consultorios: MedicoConsultorioItem[];
}

// ─── EXCEPCIONES ─────────────────────────────────────────────────────────────

export interface MedicoExcepcionItem {
  id: number;
  tipo: TipoExcepcion;
  fechaInicio: string;
  fechaFin: string;
  horaInicio: string | null;
  horaFin: string | null;
  motivo: string | null;
  consultorioId: number | null;
}

// ─── COBERTURAS ──────────────────────────────────────────────────────────────

export interface MedicoCoberturaHorarioItem {
  id: number;
  diaSemana: DiaSemana;
  horaInicio: string;
  horaFin: string;
}

export interface MedicoCoberturaItem {
  id: number;
  medicoSuplenteId: number;
  medicoSuplenteNombre: string;
  medicoTitularId: number;
  medicoTitularNombre: string;
  consultorioId: number | null;
  consultorioNombre: string | null;
  centroId: number | null;
  centroNombre: string | null;
  fechaInicio: string;
  fechaFin: string | null;
  motivo: MotivoCobertura;
  isActive: boolean;
  horarios: MedicoCoberturaHorarioItem[];
  createdAt: string | null;
}

// ─── DISPONIBILIDAD ──────────────────────────────────────────────────────────

export interface MedicoDisponible {
  /** CatMedico.id (No. Médico): espacio MÉDICO (agenda, slots, citas). */
  medicoId: number;
  /** SyUsuario del médico: espacio USUARIO (Visit.doctorId). null = no puede atender visitas. */
  usuarioId: number | null;
  nombreCompleto: string;
  servicio: string | null;
  tipoMedico: TipoMedico;
  disponible: boolean;
  consultorioId?: number;
  consultorioNumero?: number;
  consultorioNombre?: string;
  centroId?: number;
  origen?: "COBERTURA" | "REGULAR";
  horaInicio?: string;
  horaFin?: string;
  intervaloCitaMin?: number;
  motivo?: string;
}

export interface MedicosDisponiblesResponse {
  fecha: string;
  centroId: number;
  medicos: MedicoDisponible[];
}

// ─── REQUESTS ────────────────────────────────────────────────────────────────

export interface CreateMedicoRequest {
  usuarioId: number;
  tipoMedico?: TipoMedico;
  servicio?: string | null;
  observaciones?: string | null;
}

export interface AsignarUsuarioRequest {
  usuarioId: number;
}

/** Datos del CatMedico que NO se movieron porque el usuario ya tenía un valor propio. */
export interface AsignarUsuarioDescartados {
  nombre?: string;
  paterno?: string;
  materno?: string;
  cedulaProfesional?: string;
}

export interface AsignarUsuarioResponse extends MedicoListItem {
  descartados: AsignarUsuarioDescartados;
}

export interface UpdateMedicoRequest {
  tipoMedico?: TipoMedico;
  servicio?: string | null;
  observaciones?: string | null;
  estatusMedico?: EstatusMedico;
}

export interface AddEspecialidadRequest {
  especialidadId: number;
  esPrincipal?: boolean;
}

export interface AddCentroRequest {
  centroId: number;
  tipoAdscripcion?: TipoAdscripcion;
  fechaInicio: string;
  fechaFin?: string | null;
}

export interface AddConsultorioRequest {
  consultorioId: number;
  tipoAsignacion?: TipoAsignacion;
  fechaInicio: string;
  fechaFin?: string | null;
  horarios?: {
    diaSemana: DiaSemana;
    horaInicio: string;
    horaFin: string;
    intervaloCitaMin?: number;
    canal?: CanalAtencion;
  }[];
}

export interface SaveHorarioRequest {
  horarios: {
    diaSemana: DiaSemana;
    horaInicio: string;
    horaFin: string;
    intervaloCitaMin?: number;
    canal?: CanalAtencion;
  }[];
}

export interface CreateExcepcionRequest {
  tipo: TipoExcepcion;
  fechaInicio: string;
  fechaFin: string;
  horaInicio?: string | null;
  horaFin?: string | null;
  consultorioId?: number | null;
  motivo?: string | null;
}

export interface CreateCoberturaRequest {
  medicoSuplenteId: number;
  medicoTitularId: number;
  consultorioId: number;
  centroId: number;
  fechaInicio: string;
  fechaFin: string;
  motivo?: MotivoCobertura;
  horarios?: { diaSemana: DiaSemana; horaInicio: string; horaFin: string }[];
}

// ─── RESPONSES ───────────────────────────────────────────────────────────────

export interface MedicosListResponse {
  items: MedicoListItem[];
  total: number;
}

export interface MedicoDetailResponse {
  medico: MedicoDetail;
}

export interface MedicoExcepcionesResponse {
  items: MedicoExcepcionItem[];
}

export interface MedicoCoberturasResponse {
  items: MedicoCoberturaItem[];
}

// ─── IMPORTACIÓN MASIVA (EXCEL) ───────────────────────────────────────────────

/**
 * Datos normalizados de una fila del Excel de importación.
 * Columnas de origen (en este orden exacto):
 * No. Médico | Usuario (Login del sistema) | Nombre(s) | Apellido Paterno |
 * Apellido Materno | Cédula Profesional | Escuela (ID) |
 * Clave Clínica (legado) | Especialidad (ID) | Servicio |
 * Estatus del Médico
 *
 * `tipoMedico` y `observaciones` ya no vienen en la plantilla: el backend
 * devuelve siempre "CLINICA" y null.
 *
 * `noMedico` (opcional) es el `CatMedico.id` explícito; null = toma el
 * siguiente de la secuencia. `usuario` vacío = médico sin usuario: paterno y
 * nombre son obligatorios y se guardan en el propio médico. Con usuario,
 * paterno/materno/nombre son null (se toman del usuario).
 * `centroId` / `especialidadId` / `escuelaId` son null cuando la clave o el
 * nombre no coinciden (la fila trae un warning, no un error). La escuela solo
 * aplica sin usuario (con usuario `escuela` y `escuelaId` son null).
 */
export interface MedicoImportRowData {
  noMedico: number | null;
  usuario: string;
  usuarioId: number | null;
  paterno: string | null;
  materno: string | null;
  nombre: string | null;
  cedulaProfesional: string | null;
  escuela: string | null;
  escuelaId: number | null;
  claveClinica: number | null;
  centroId: number | null;
  especialidad: string | null;
  especialidadId: number | null;
  tipoMedico: TipoMedico;
  servicio: string | null;
  estatusMedico: EstatusMedico;
  observaciones: string | null;
}

/**
 * Fila procesada de la importación. `errors` bloquean el lote;
 * `warnings` son informativos y NO bloquean la confirmación.
 */
export interface MedicoImportRow {
  row: number;
  data: MedicoImportRowData;
  errors: string[];
  warnings: string[];
}

/**
 * Response de preview/confirm de importación masiva.
 * POST /api/v1/medicos/import/preview
 * POST /api/v1/medicos/import/confirm
 *
 * A diferencia del import de usuarios, médicos no envía correos -- no hay
 * campo `emailFailures` en esta response.
 */
export interface MedicoImportResult {
  totalRecords: number;
  totalErrores: number;
  totalWarnings: number;
  inserted: number;
  rows: MedicoImportRow[];
}

export type MedicoImportJobStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCESS"
  | "VALIDATION_FAILED"
  | "ERROR";

export type MedicoImportJobPhase = "QUEUED" | "VALIDATING" | "SAVING" | "DONE";

/**
 * Estado de un import de médicos en segundo plano (Celery).
 * POST /api/v1/medicos/import/confirm      -> 202 con este payload
 * GET  /api/v1/medicos/import/jobs/:jobId  -> polling hasta status final
 *
 * `processed`/`phaseTotal` son el avance DENTRO de la fase actual (en SAVING,
 * médicos guardados / total). `result` solo viene con status final.
 */
export interface MedicoImportJob {
  jobId: string;
  status: MedicoImportJobStatus;
  phase: MedicoImportJobPhase;
  processed: number;
  phaseTotal: number;
  totalRecords: number;
  inserted: number;
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  result: MedicoImportResult | null;
}
